# Technical Design Document — CR-001: Business Modeling and Target Construction

This document specifies the technical design, schemas, performance optimization strategies, and data quality containment logic for the target construction pipeline.

---

## 📐 Mathematical Formulation of Metrics

Let $u$ represent a user, and $T_{obs}$ represent the observation (cut-off) date.

### 1. Monthly Volume ($V_u(T_{obs})$)
The volume is the total loan amount disbursed to user $u$ in the 30-day window ending on the observation date:
$$V_u(T_{obs}) = \sum_{l \in L_u} \text{amount}(l) \times \mathbb{I}\left( T_{obs} - 30 \le \text{disbursement\_date}(l) \le T_{obs} \right)$$
Where:
- $L_u$ is the set of all loans disbursed to user $u$.
- $\mathbb{I}(\cdot)$ is the indicator function.

### 2. Session Regularity ($R_u(T_{obs})$)
Session regularity is defined as the count of distinct calendar days in UTC where the user has at least one logged session in the 30-day window ending on the observation date:
$$R_u(T_{obs}) = \left| \{ \text{date}(s) \mid s \in S_u \land T_{obs} - 30 \le \text{date}(s) \le T_{obs} \} \right|$$
Where:
- $S_u$ is the set of all sessions logged for user $u$.
- $\text{date}(s)$ extracts the UTC date from the session timestamp.

### 3. Target Default Indicator ($Y_u(T_{obs})$)
The binary target variable indicates whether the user defaults (exceeds 30 Days Past Due) on any payment due within the 12-month performance window following the observation date:
$$Y_u(T_{obs}) = \max_{p \in P_u(T_{obs})} \mathbb{I}\left( \text{DPD}(p) > 30 \right)$$
Where:
- $P_u(T_{obs})$ is the set of all payments associated with user $u$'s loans that have a due date in the interval $(T_{obs}, T_{obs} + 12 \text{ months}]$.
- The Days Past Due ($\text{DPD}$) for a payment installment $p$ is calculated as:
  $$\text{DPD}(p) = \begin{cases} 
      \text{payment\_date}(p) - \text{due\_date}(p) & \text{if payment\_date}(p) \text{ is not NULL} \\
      T_{current} - \text{due\_date}(p) & \text{if payment\_date}(p) \text{ is NULL} \text{ and } T_{current} > \text{due\_date}(p) \\
      0 & \text{otherwise}
  \end{cases}$$
  Here, $T_{current}$ represents the date the table is generated or when the pipeline is evaluated.

---

## 🗄️ Database Schemas & Data Model

### Staging/Source Tables (BigQuery)

#### 1. `raw.users`
| Column Name | Data Type | Mode | Description |
| :--- | :--- | :--- | :--- |
| `user_id` | STRING | REQUIRED | Unique user identifier (PK) |
| `created_at` | TIMESTAMP | REQUIRED | Account creation timestamp |
| `country` | STRING | REQUIRED | Two-letter country code (e.g. BR, MX, AR) |
| `updated_at` | TIMESTAMP | REQUIRED | Record update timestamp |
| `ingestion_timestamp` | TIMESTAMP | REQUIRED | Ingestion track |

#### 2. `raw.user_sessions`
| Column Name | Data Type | Mode | Description |
| :--- | :--- | :--- | :--- |
| `session_id` | STRING | REQUIRED | Unique session identifier (PK) |
| `user_id` | STRING | REQUIRED | User identifier (FK) |
| `session_timestamp` | TIMESTAMP | REQUIRED | Time of session start |

#### 3. `raw.loans`
| Column Name | Data Type | Mode | Description |
| :--- | :--- | :--- | :--- |
| `loan_id` | STRING | REQUIRED | Unique loan identifier (PK) |
| `user_id` | STRING | REQUIRED | Borrower identifier (FK) |
| `disbursement_date` | DATE | REQUIRED | Date loan was disbursed |
| `amount` | NUMERIC | REQUIRED | Loan principal amount |
| `term_months` | INT64 | REQUIRED | Loan duration in months |
| `updated_at` | TIMESTAMP | REQUIRED | Record update timestamp |
| `ingestion_timestamp` | TIMESTAMP | REQUIRED | Ingestion track |

#### 4. `raw.loan_payments`
| Column Name | Data Type | Mode | Description |
| :--- | :--- | :--- | :--- |
| `payment_id` | STRING | REQUIRED | Unique payment installment identifier (PK) |
| `loan_id` | STRING | REQUIRED | Associated loan identifier (FK) |
| `due_date` | DATE | REQUIRED | Due date of installment |
| `payment_date` | DATE | NULLABLE | Date payment was made |
| `amount_due` | NUMERIC | REQUIRED | Installment amount due |
| `amount_paid` | NUMERIC | REQUIRED | Installment amount paid |
| `updated_at` | TIMESTAMP | REQUIRED | Record update timestamp |
| `ingestion_timestamp` | TIMESTAMP | REQUIRED | Ingestion track |

### Target Analytical Table

#### `credit_risk.target_construction`
| Column Name | Data Type | Mode | Description |
| :--- | :--- | :--- | :--- |
| `user_id` | STRING | REQUIRED | Unique borrower identifier (PK) |
| `observation_date` | DATE | REQUIRED | Observation snapshot date (Partition Key) |
| `monthly_volume` | NUMERIC | REQUIRED | Loan principal volume in past 30 days |
| `session_regularity` | INT64 | REQUIRED | Distinct active days in past 30 days |
| `target_default_30d` | INT64 | REQUIRED | Default target indicator (0 or 1) |

---

## ⚡ HPC (High-Performance Computing) Strategies

To ensure sub-minute response times and optimize BigQuery slots consumption on large datasets:
1. **Partitioning:** The target table `credit_risk.target_construction` SHALL be partitioned by `observation_date` using daily partitioning. This allows downstream models and analysis queries to scan only specific cohorts.
2. **Clustering:** The target table SHALL be clustered by `user_id`. Joins with user demographics or downstream prediction tables will execute map-side merge joins.
3. **Incremental Merge (Idempotency):** Calculations are processed per monthly observation snapshot. When updates or corrections occur, the target partitions are overwritten using:
   ```sql
   MERGE INTO credit_risk.target_construction T
   USING (SELECT ... FROM features_source) S
   ON T.user_id = S.user_id AND T.observation_date = S.observation_date
   WHEN MATCHED THEN UPDATE SET ...
   WHEN NOT MATCHED THEN INSERT ...
   ```

---

## 🛡️ AI Logical Anomaly Containment & Data Quality Rules

To mitigate upstream dirty data (duplicate primary keys, timestamp corruption, malformed string dates):

1. **PK Deduplication Strategy (`A5`):**
   Prior to feature aggregation, a Common Table Expression (CTE) deduplicates entities using:
   ```sql
   WITH deduplicated_loans AS (
     SELECT * EXCEPT(row_num)
     FROM (
       SELECT *, ROW_NUMBER() OVER(
         PARTITION BY loan_id 
         ORDER BY updated_at DESC, ingestion_timestamp DESC
       ) as row_num
       FROM raw.loans
     )
     WHERE row_num = 1
   )
   ```
2. **Date Parsing Robustness (`A6`):**
   Upstream dates might contain formats such as `YYYY/MM/DD` or `DD-MM-YYYY`.
   - The query SHALL use `SAFE_CAST(col AS DATE)` or `SAFE.PARSE_DATE('%Y-%m-%d', col)` to prevent SQL execution failures.
   - Any record with an unparseable date field (resulting in `NULL`) will be flagged in the data quality logs and excluded from downstream metrics.
3. **Null Primary Keys (`A6`):**
   Any staging records where the natural key (`user_id`, `loan_id`, `payment_id`, or `session_id`) is `NULL` SHALL be filtered out of processing immediately.
4. **Timezone Illusion Containment:**
   All session timestamps (`session_timestamp`) are converted to standard UTC using `DATETIME(session_timestamp, 'UTC')` to avoid timezone offset mismatches.
