# Traceability Mapping — CR-001: Medallion DuckDB Prefect Pipeline

This document maps the analytical requirements defined in `requirements.md` to the verification tests implemented in `tests/test_medallion_pipeline.py`.

## 📈 Requirement-to-Test Mapping Table

| Requirement ID | Requirement Name | Verification Test Method | Test Location |
| :--- | :--- | :--- | :--- |
| **A1** | Monthly Transaction Volume | `test_monthly_volume` | [`tests/test_medallion_pipeline.py`](file:///D:/credit-risk-MELI/tests/test_medallion_pipeline.py) |
| **A2** | Session Regularity | `test_session_regularity` | [`tests/test_medallion_pipeline.py`](file:///D:/credit-risk-MELI/tests/test_medallion_pipeline.py) |
| **A3** | Target Default Indicator (DPD30) | `test_target_default_indicator` | [`tests/test_medallion_pipeline.py`](file:///D:/credit-risk-MELI/tests/test_medallion_pipeline.py) |
| **A4** | Bronze Raw Load | `test_bronze_raw_load` | [`tests/test_medallion_pipeline.py`](file:///D:/credit-risk-MELI/tests/test_medallion_pipeline.py) |
| **A5** | Silver Cleaning & Deduplication | `test_silver_deduplication_and_normalization` | [`tests/test_medallion_pipeline.py`](file:///D:/credit-risk-MELI/tests/test_medallion_pipeline.py) |
| **A6** | Silver Date & Type Normalization | `test_silver_deduplication_and_normalization` | [`tests/test_medallion_pipeline.py`](file:///D:/credit-risk-MELI/tests/test_medallion_pipeline.py) |
| **A7** | Cohort Default Rate Alerting | `test_cohort_default_alert` | [`tests/test_medallion_pipeline.py`](file:///D:/credit-risk-MELI/tests/test_medallion_pipeline.py) |
| **A8** | Prefect Flow Orchestration | `test_prefect_flow_orchestration` | [`tests/test_medallion_pipeline.py`](file:///D:/credit-risk-MELI/tests/test_medallion_pipeline.py) |

---

## 🔍 Verification Details

### `A1: Monthly Transaction Volume`
* **Requirement**: Slices all loans in the 30 days prior to and including the observation date, calculating total loan volume using `COALESCE(SUM(amount), 0.0)`.
* **Verification**: `test_monthly_volume` verifies that `user_1` volume includes only the loan disbursed on `2024-12-10` and excludes the one disbursed on `2024-11-15` (which is outside the 30-day window).

### `A2: Session Regularity`
* **Requirement**: Slices sessions in the 30-day window and calculates unique dates of session activity.
* **Verification**: `test_session_regularity` verifies that `user_1` has 2 unique calendar days of activity within the 30-day window, even though multiple sessions occurred on one day and one session was outside the window.

### `A3: Target Default Indicator`
* **Requirement**: Slices payments due in the 12-month window following the observation date, calculating default if DPD exceeds 30.
* **Verification**: `test_target_default_indicator` verifies that `user_1` is flagged as a defaulter (`target_default_30d = 1`) due to a payment paid 46 days late, while `user_2` (whose payments are <= 30 DPD) and `user_3` (who has no payments) are not defaulted.

### `A4: Bronze Raw Load`
* **Requirement**: Raw records are ingested into Bronze tables append-only, preserving all duplicates and NULL primary key records.
* **Verification**: `test_bronze_raw_load` verifies that the row counts in the Bronze tables match the raw data counts (e.g. 5 users, 7 sessions) including all duplicates and null keys.

### `A5: Silver Cleaning & Deduplication`
* **Requirement**: Deduplicates using `ROW_NUMBER() OVER (PARTITION BY pk ORDER BY updated_at DESC, ingestion_timestamp DESC)` and filters out rows with NULL primary or foreign keys.
* **Verification**: `test_silver_deduplication_and_normalization` verifies that duplicate primary keys are correctly resolved and rows with NULL primary keys (or missing key connections like missing `user_id` in sessions/loans) are excluded from the Silver tables.

### `A6: Silver Date & Type Normalization`
* **Requirement**: Parses dates from formats (slashes, dashes) using `strptime` or `TRY_CAST` and casts amounts to `DOUBLE`.
* **Verification**: `test_silver_deduplication_and_normalization` verifies that slash formats like `2024/12/20` and dash formats like `2024-12-10` are parsed correctly, and numeric amounts are correctly cast to double float types.

### `A7: Cohort Default Rate Alerting`
* **Requirement**: Warning log and diagnostic report are compiled if the cohort default rate for any registration month exceeds 15% in Gold.
* **Verification**: `test_cohort_default_alert` triggers the alert and verifies that the generated warning report lists the `2024-05` cohort (default rate 100%) and excludes `2024-06` (default rate 0%).

### `A8: Prefect Flow Orchestration`
* **Requirement**: Tasks for Bronze, Silver, Gold, and Alerts run sequentially under Prefect flow control.
* **Verification**: `test_prefect_flow_orchestration` runs the parent `medallion_pipeline_flow` and asserts that all task execution stages complete successfully and return expected pipeline execution metrics.
