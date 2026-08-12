# Implementation Tasks Checklist — CR-001: Business Modeling and Target Construction

This document lists the step-by-step implementation tasks required to build the business modeling and target construction pipeline.

---

## 📋 Tasks Checklist

### Phase 1: Environment & Schema Inception
- [ ] **Task 1: Define Target BigQuery Tables and Setup Mock Data Harness**
      Create mock tables matching the BigQuery schemas defined in `design.md` inside a local SQLite database (for unit testing) and BigQuery schema creation scripts.
      *Requirement Mapping:* None (Infrastructure setup)

### Phase 2: Data Quality & Auditing
- [ ] **Task 2: Implement Data Audit and Deduplication SQL Logic**
      Write a SQL query template/file `src/data/queries/audit_data.sql` that isolates duplicates, parses malformed date formats safely, filters out null primary keys, and records validation anomalies.
      *Requirement Mapping:* `A5`, `A6`

### Phase 3: Feature & Target Extraction SQL Queries
- [ ] **Task 3: Implement Feature Extraction SQL Query**
      Write a SQL query template `src/data/queries/extract_features.sql` to calculate the user behavior metrics: monthly loan volume (`monthly_volume`) and session regularity (`session_regularity`).
      *Requirement Mapping:* `A1`, `A2`

- [ ] **Task 4: Implement Target Construction SQL Query**
      Write a SQL query template `src/data/queries/build_target.sql` that computes `target_default_30d` by evaluating installment repayment delays within the 12-month performance window following the cohort observation date.
      *Requirement Mapping:* `A3`

- [ ] **Task 5: Implement Idempotent Database Ingestion Query**
      Write the BigQuery `MERGE` SQL template `src/data/queries/merge_target_construction.sql` that combines target constructions with existing tables partition-by-partition.
      *Requirement Mapping:* `A4`

### Phase 4: Testing & Verification
- [ ] **Task 6: Design Unit and Integration Tests**
      Develop a Python test module `tests/test_target_construction.py` containing test cases that verify calculations for monthly volume, session regularity, target definition, primary key deduplication, date parsing, and the 15% alerting threshold. Add these to the test suite so they run with `init.sh`.
      *Requirement Mapping:* `A1`, `A2`, `A3`, `A4`, `A5`, `A6`, `A7`

### Phase 5: Pipeline Integration (Mandatory Orchestrator)
- [ ] **Task 7: Create the Unified Pipeline Orchestrator Script**
      Create a single, unified Python script `src/data/target_construction.py` that aggregates and executes all operations, database queries (audit, extract features, build target, merge), and prints a brief validation report summarizing cohort default rates (triggering warning logs if any cohort exceeds the 15% rate).
      *Requirement Mapping:* All (`A1` - `A7`)
