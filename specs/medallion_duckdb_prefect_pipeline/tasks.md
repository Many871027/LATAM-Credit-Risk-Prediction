# Implementation Tasks Checklist — CR-001: Medallion DuckDB Prefect Pipeline

This document lists the step-by-step implementation tasks required to build the Medallion database pipeline using DuckDB and Prefect.

---

## 📋 Tasks Checklist

### Phase 1: Cleanup & Environment Inception

- [x] **Task 1: Obsolete SQLite Cleanup & DuckDB Test Suite Setup**
      Remove obsolete SQLite-based test harness (`tests/mock_db_harness.py`, `tests/test_target_construction.py`), and delete/update obsolete SQLite-based target construction queries (`src/data/queries/*.sql`). Define the skeleton for a DuckDB-based test suite in `tests/test_medallion_pipeline.py`.
      *Requirement Mapping:* None (Infrastructure / Cleanup)

- [x] **Task 2: Define DuckDB Medallion Database Schemas**
      Write SQL DDL statements or write Python setup functions to define and initialize the `bronze`, `silver`, and `gold` schemas and tables in DuckDB as specified in `design.md`.
      *Requirement Mapping:* `A4`, `A5`, `A6`, `A7`

### Phase 2: Prefect Pipeline Tasks

- [x] **Task 3: Implement Bronze Raw Ingestion Task**
      Create a Prefect task `ingest_to_bronze_task` to insert raw JSON/dictionary records into Bronze tables append-only, preserving all duplicates and NULL primary key records.
      *Requirement Mapping:* `A4`

- [x] **Task 4: Implement Silver Cleaning and Deduplication Task**
      Create a Prefect task `transform_to_silver_task` that runs DuckDB SQL statements to:
      1. Deduplicate records using `ROW_NUMBER() OVER (PARTITION BY pk ORDER BY updated_at DESC, ingestion_timestamp DESC)`.
      2. Filter out rows with NULL primary or foreign keys.
      3. Clean and parse date fields of varying formats using `TRY_CAST` or `strptime` into ISO `DATE`/`TIMESTAMP` format.
      4. Cast amounts to `DOUBLE`.
      *Requirement Mapping:* `A5`, `A6`

- [x] **Task 5: Implement Gold Feature & Target Construction Task**
      Create a Prefect task `build_gold_features_task` to run DuckDB SQL queries that calculate for a given `observation_date`:
      1. User monthly volume (`monthly_volume`) over the last 30 days.
      2. User session regularity (`session_regularity`) count of distinct days in the last 30 days.
      3. User default status (`target_default_30d`) indicating if any payment installment due within 12 months past the observation date was unpaid or paid >30 days late.
      4. Idempotently insert/merge the results into `gold.target_construction`.
      *Requirement Mapping:* `A1`, `A2`, `A3`

- [x] **Task 6: Implement Quality Alerting Task**
      Create a Prefect task `run_alerts_task` that queries the Gold cohort features, calculates default rates by registration month, and logs warning alerts or generates a drift report if any cohort default rate exceeds 15%.
      *Requirement Mapping:* `A7`

### Phase 3: Integration & Testing

- [x] **Task 7: Build the Prefect Flow Orchestrator**
      Build the parent Prefect flow `medallion_pipeline_flow` coordinating the tasks in sequence, adding retry policies (3 retries, 10s delay) for transient database errors.
      *Requirement Mapping:* `A8`

- [x] **Task 8: Complete DuckDB-based Unit and Integration Test Suite**
      Implement the tests in `tests/test_medallion_pipeline.py` using DuckDB's in-memory mode, verifying the Bronze loading, Silver deduplication/cleaning, Gold target construction correctness, and alerting rules. Ensure the test suite runs and passes green under `./init.sh`.
      *Requirement Mapping:* `A1` to `A8`

### Phase 4: Unified Execution

- [x] **Task 9: Create the Unified Pipeline Orchestration Script**
      Create a single, unified Python script (e.g., `src/data/run_pipeline.py` or similar location under `src/data/`) that aggregates and executes all operations, queries, and report generation procedures defined in the preceding tasks of that specification (i.e. initializing schemas, running the Prefect flow for a cohort, and printing the cohort summary/drift report).
      *Requirement Mapping:* All (`A1` - `A8`)
