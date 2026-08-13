# Implementation Tasks Checklist — CR-004: Drift Monitoring and Logging

This document lists the step-by-step implementation tasks required to build the prediction telemetry database loggers, custom dialogue safety scorers, PSI drift calculator, and MLflow integration.

---

## 📋 Tasks Checklist

### Phase 1: Environment Setup & Directory Initialization

- [x] **Task 1: Setup Directory Structure and Define Modules**
      Create the `src/monitoring` directory if it does not exist. Declare empty Python files:
      1. `src/monitoring/logging_db.py` - database logging utilities.
      2. `src/monitoring/scorers.py` - custom dialogue scorers.
      3. `src/monitoring/drift.py` - PSI computation and drift monitoring pipeline.
      *Requirement Mapping:* None (Infrastructure Setup)

### Phase 2: Schema Creation & Ingestion Instrument

- [x] **Task 2: Implement Database Table Schema Setup**
      Write DuckDB SQL schemas and code in `src/monitoring/logging_db.py` to check for and create the tables `gold.prediction_logs`, `gold.dialogue_logs`, and `gold.drift_metrics` inside the database.
      *Requirement Mapping:* `A2`, `A3`, `A4`

- [x] **Task 3: Instrument Inference API Prediction Logging**
      Modify `src/api/main.py` (and the endpoint `/predict`) to record and insert incoming prediction request features, outputs, latency, status, and anomaly flags into `gold.prediction_logs` asynchronously or in a background task after each prediction. If any required field is NULL, ensure the `is_anomaly` flag is set to true.
      *Requirement Mapping:* `A2`, `A6`

### Phase 3: Custom dialogue Scorers & PSI Formulation

- [x] **Task 4: Implement Custom Dialogue Evaluation Scorers**
      Implement `ToxicityScorer`, `PromptInjectionScorer`, and `FidelityScorer` in `src/monitoring/scorers.py` as designed in the technical design document, ensuring they process text inputs and return numerical scores between 0.0 and 1.0.
      *Requirement Mapping:* `A3`

- [x] **Task 5: Implement PSI Calculation Mathematics**
      In `src/monitoring/drift.py`, implement the function `calculate_psi(expected: np.ndarray, actual: np.ndarray, num_bins: int = 10) -> float`. The function must:
      1. Calculate bin edges on the expected data using quantiles.
      2. Apply epsilon smoothing ($\epsilon = 1\times 10^{-4}$) to prevent divisions by zero or logarithmic errors.
      3. Compute and return the population stability index value.
      *Requirement Mapping:* `A1`

### Phase 4: Drift Pipeline & MLflow Integration

- [x] **Task 6: Implement Weekly Drift Evaluation Pipeline**
      Write a function `run_weekly_drift_analysis(db_path: str, reference_date: str)` in `src/monitoring/drift.py` that:
      1. Queries prediction logs for the week and extracts features and predictions.
      2. Queries the training baseline from `gold.target_construction` or cached baseline profiles.
      3. Computes PSI for features (`monthly_volume`, `session_regularity`, `income`, `probability_of_default`).
      4. Evaluates dialogue safety scores and triggers a warning log/alert status if toxicity averages exceed 0.20 or injection rates exceed 5%.
      5. Appends the computed metrics to `gold.drift_metrics`.
      *Requirement Mapping:* `A1`, `A4`, `A7`

- [x] **Task 7: Implement MLflow Drift Logging**
      In `src/monitoring/drift.py`, integrate MLflow logging into the weekly drift analysis. Set the active experiment to `drift_monitoring_and_logging`, start an MLflow run, and log all computed PSI values, average dialogue safety scores, parameters (total predictions evaluated, start/end timestamps), and binary alert flags.
      *Requirement Mapping:* `A5`

### Phase 5: Verification & Automated Tests

- [x] **Task 8: Implement Automated Telemetry & Drift Tests**
      Create a test file `tests/test_monitoring.py` to test the monitoring functions:
      1. Verification of database table creation.
      2. Unit tests for `ToxicityScorer`, `PromptInjectionScorer`, and `FidelityScorer`.
      3. Mathematical verification of PSI calculation using controlled mock distributions (stable vs. drifted).
      4. Verification of MLflow logging execution and correct parameter/metric storage.
      *Requirement Mapping:* `A1` to `A7`

### Phase 6: Unified Pipeline Execution Script

- [x] **Task 9: Create Unified Drift Monitoring Execution and Verification Script**
      Create a single, unified Python script `src/monitoring/run_drift_verification.py` that aggregates and executes all operations, queries, and report generation procedures defined in the preceding tasks of this specification. The script must:
      1. Automatically initialize database logging tables if they do not exist.
      2. Populate `gold.prediction_logs` and `gold.dialogue_logs` with realistic test datasets (simulating both a stable week and a drifted week with safety violations).
      3. Run the weekly drift analysis function to calculate PSI and safety scores.
      4. Log the results to a local MLflow registry.
      5. Print a consolidated text-based drift monitoring report displaying PSI scores, safety indicators, alert statuses, and MLflow run details.
      *Requirement Mapping:* All (`A1` - `A7`)
