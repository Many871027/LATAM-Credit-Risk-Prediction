# Analytical Requirements Specification — CR-001: Medallion DuckDB Prefect Pipeline

This document details the analytical requirements for the credit risk feature **CR-001 (medallion_duckdb_prefect_pipeline)**.

## 📊 Business Acceptance Criteria Mapping
The business acceptance criteria defined in `feature_list.json` are mapped to the analytical requirements below:
- **Criterion 1 (Bronze Ingestion):** Covered by **A4** (Bronze Raw Load).
- **Criterion 2 (Silver Cleaning & Deduplication):** Covered by **A5** (PrimaryKey Deduplication) and **A6** (Type & Date Normalization).
- **Criterion 3 (Gold Generation & Features):** Covered by **A1** (Monthly Volume), **A2** (Session Regularity), and **A3** (Target Default 30D).
- **Criterion 4 (Prefect Orchestration & Fault Tolerance):** Covered by **A7** (Cohort Alerting Monitoring) and **A8** (Prefect Flow Orchestration).

---

## 🔤 Analytical Requirements (EARS-BI Notation)

### 1. Ubiquitous (Base & Immutable Metrics)

*   **A1: Monthly Transaction Volume**
    *   *Requirement*: The analytical layer SHALL calculate user-level monthly transaction volume (`monthly_volume`) using the `COALESCE(SUM(amount), 0.0)` function over all disbursed loans in `silver.loans` in the 30 days prior to and including the observation date, grouped by `user_id`.
    *   *Grain*: `user_id` + `observation_date`

*   **A2: Session Regularity**
    *   *Requirement*: The analytical layer SHALL calculate user-level session regularity (`session_regularity`) using the count of distinct calendar days (`COUNT(DISTINCT CAST(session_timestamp AS DATE))`) on which a session was recorded in `silver.user_sessions` in the 30 days prior to and including the observation date, grouped by `user_id`.
    *   *Grain*: `user_id` + `observation_date`

*   **A3: Target Default Indicator (target_default_30d)**
    *   *Requirement*: The analytical layer SHALL calculate the binary default target variable `target_default_30d` using a conditional check (`MAX(CASE WHEN days_past_due > 30 THEN 1 ELSE 0 END)`) indicating whether the user had any installment payment due in `silver.loan_payments` within the 12-month performance window following the observation date that remained unpaid or was paid more than 30 days past its due date, grouped by `user_id`.
    *   *Grain*: `user_id` + `observation_date`

### 2. Event-Driven (ETL / Ingestion Strategies)

*   **A4: Bronze Raw Load**
    *   *Requirement*: WHEN the Prefect flow is executed, the pipeline SHALL ingest raw transaction and customer records into the DuckDB Bronze tables (`bronze.users`, `bronze.user_sessions`, `bronze.loans`, `bronze.loan_payments`) using an append-only/insert strategy to preserve all raw duplicates and NULL values.

*   **A5: Silver Cleaning & Deduplication**
    *   *Requirement*: WHEN the Silver pipeline task is triggered, the pipeline SHALL execute a deduplication query using `ROW_NUMBER() OVER (PARTITION BY pk ORDER BY updated_at DESC, ingestion_timestamp DESC)` to isolate the most recent state of each record, filter out any rows with NULL primary or foreign keys (`user_id`, `session_id`, `loan_id`, `payment_id`), and load the result into the DuckDB Silver tables (`silver.users`, `silver.user_sessions`, `silver.loans`, `silver.loan_payments`).

*   **A6: Silver Date & Type Normalization**
    *   *Requirement*: WHEN the Silver pipeline task is triggered, the pipeline SHALL clean raw inputs by parsing dates in formats such as `YYYY/MM/DD` or `YYYY-MM-DD` using `strptime` or `TRY_CAST` to yield standard ISO `DATE`/`TIMESTAMP` types, and cast amounts to `DOUBLE` value types, logging any parsing exceptions.

### 3. Unwanted Behavior (Data Governance & Quality)

*   **A7: Cohort Default Rate Alerting**
    *   *Requirement*: IF the average monthly default rate (`AVG(target_default_30d)`) for any cohort grouped by user registration month exceeds 15% in the Gold table for the evaluated cohort, the pipeline SHALL log a quality warning alert and compile a diagnostic report summarizing registration cohort metrics.

### 4. State-Driven (AI Alerting Thresholds)

*   **A8: Prefect Flow Orchestration**
    *   *Requirement*: WHILE executing the database pipeline, the Prefect orchestrator SHALL process the Bronze, Silver, Gold, and Alerting tasks sequentially, executing up to 3 retries with a 10-second delay for transient database lock exceptions, and logging the execution status of every task.

---

## 📥 Input & Output Data Definitions

### Inputs
1.  **Raw Data sources**:
    - `users`: User registration and country metadata.
    - `user_sessions`: Timestamps of user activity.
    - `loans`: Amount, disbursement date, term length.
    - `loan_payments`: Due date, payment date, amounts due and paid.

### Outputs
1.  **`gold.target_construction`**: The final analytics-ready DuckDB table containing aggregated behavior metrics and default targets per user cohort.
