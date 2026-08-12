# Analytical Requirements Specification — CR-001: Business Modeling and Target Construction

This document details the analytical requirements for the credit risk feature **CR-001 (business_modeling_and_target_construction)**.

## 📊 Business Acceptance Criteria Mapping
The business acceptance criteria defined in `feature_list.json` are mapped to the analytical requirements below:
- **Criterion 1 (Historical Variables):** Covered by **A1** (Monthly Volume) and **A2** (Session Regularity).
- **Criterion 2 (Target Construction):** Covered by **A3** (Target Default 30D).
- **Criterion 3 (Data Audit & Governance):** Covered by **A5** (PrimaryKey Deduplication) and **A6** (Type and Null Validation).

---

## 🔤 Analytical Requirements (EARS-BI Notation)

### 1. Ubiquitous (Base & Immutable Metrics)

*   **A1: Monthly Transaction Volume**
    *   *Requirement*: The analytical layer SHALL calculate user-level monthly transaction volume (`monthly_volume`) using the `COALESCE(SUM(amount), 0)` function over all disbursed loans in the 30 days prior to the observation date, grouped by `user_id`.
    *   *Grain*: `user_id` + `observation_date`

*   **A2: Session Regularity**
    *   *Requirement*: The analytical layer SHALL calculate user-level session regularity (`session_regularity`) using the count of distinct calendar days (`COUNT(DISTINCT DATE(session_timestamp))`) on which a session was recorded for the user in the 30 days prior to the observation date, grouped by `user_id`.
    *   *Grain*: `user_id` + `observation_date`

*   **A3: Target Default Indicator (target_default_30d)**
    *   *Requirement*: The analytical layer SHALL calculate the binary default target variable `target_default_30d` using a conditional check (`MAX(CASE WHEN days_past_due > 30 THEN 1 ELSE 0 END)`) indicating whether the user had any installment payment due within the 12-month performance window following the observation date that remained unpaid or was paid more than 30 days past its due date, grouped by `user_id`.
    *   *Grain*: `user_id` + `observation_date`

### 2. Event-Driven (ETL / Ingestion Strategies)

*   **A4: Idempotent Pipeline Execution**
    *   *Requirement*: WHEN the scheduled monthly ETL pipeline is triggered, the pipeline SHALL execute a BigQuery `MERGE` statement to update the `credit_risk.target_construction` table with idempotent behavior, overwriting existing records that match the combination of `user_id` and `observation_date`.

### 3. Unwanted Behavior (Data Governance & Quality)

*   **A5: Primary Key Deduplication**
    *   *Requirement*: IF duplicate primary keys (such as `user_id`, `loan_id`, or `payment_id`) are detected in the staging tables, the system SHALL execute a `ROW_NUMBER()` window function partitioned by the primary key and ordered by `updated_at DESC, ingestion_timestamp DESC` to isolate and retain only the most recent valid record.

*   **A6: Type Conversion and Null Resolution**
    *   *Requirement*: IF date fields or numeric amounts contain malformed formats (such as slashes in dates or non-numeric characters in amounts) or if primary keys contain NULL values, the system SHALL apply `SAFE_CAST` or `SAFE.PARSE_DATE` to convert data types, discard rows with NULL primary keys, and log the volume of discarded records.

### 4. State-Driven (AI Alerting Thresholds)

*   **A7: Cohort Default Rate Monitoring**
    *   *Requirement*: WHILE the average monthly default rate (`AVG(target_default_30d)`) for any user cohort grouped by registration month exceeds 15%, the AI agent SHALL trigger a quality warning alert, query the features database, and compile a diagnostic drift report outlining potential shift in credit profile.

---

## 📥 Input & Output Data Definitions

### Inputs
1.  **`raw.users`**: Base demographic and registration details.
2.  **`raw.user_sessions`**: User activity and session logs.
3.  **`raw.loans`**: Disbursed loan contracts.
4.  **`raw.loan_payments`**: Detailed historical payment schedules and actual payment events.

### Outputs
1.  **`credit_risk.target_construction`**: The final analytics-ready table containing user features and targets per observation cohort.
