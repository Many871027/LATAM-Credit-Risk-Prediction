# Requirement Traceability Mapping — CR-004: Drift Monitoring and Logging

This document validates that all analytical requirements (`A1` to `A7`) are thoroughly covered by automated test cases.

## 📋 Traceability Matrix

| Requirement ID | Requirement Description | Test File | Test Class & Method |
| :--- | :--- | :--- | :--- |
| **A1** | Weekly PSI Metric Calculation | `tests/test_monitoring.py` | `TestDriftMonitoringAndLogging.test_psi_calculation` |
| **A2** | Prediction Log Ingestion | `tests/test_monitoring.py` | `TestDriftMonitoringAndLogging.test_prediction_logging_anomaly_handling` |
| **A3** | LLM Dialogue Safety Scoring | `tests/test_monitoring.py` | `TestDriftMonitoringAndLogging.test_scorers` & `test_dialogue_logging` |
| **A4** | Weekly Drift Pipeline Trigger | `tests/test_monitoring.py` | `TestDriftMonitoringAndLogging.test_weekly_drift_pipeline_and_mlflow` |
| **A5** | MLflow Registry Tracking | `tests/test_monitoring.py` | `TestDriftMonitoringAndLogging.test_weekly_drift_pipeline_and_mlflow` |
| **A6** | Missing/NULL Log Anomaly Handling | `tests/test_monitoring.py` | `TestDriftMonitoringAndLogging.test_prediction_logging_anomaly_handling` |
| **A7** | LLM Drift & Warning Threshold | `tests/test_monitoring.py` | `TestDriftMonitoringAndLogging.test_weekly_drift_pipeline_and_mlflow` |

## 🧪 Verification Details

1. **PSI Mathematical Correctness (`A1`)**: 
   - `test_psi_calculation` validates that `calculate_psi` returns a score `< 0.1` for identical distributions, a score `>= 0.25` for shifted distributions, and evaluates without mathematical/log-zero errors under extreme/empty bin conditions using epsilon smoothing.
2. **Prediction Telemetry (`A2`, `A6`)**:
   - `test_prediction_logging_anomaly_handling` validates that `log_prediction` correctly persists features, prediction values, latency, decisions, and statuses. It verifies that when a mandatory field is missing/NULL, the `is_anomaly` flag is automatically resolved to `True`.
3. **LLM Safety Scoring (`A3`)**:
   - `test_scorers` verifies that `ToxicityScorer`, `PromptInjectionScorer`, and `FidelityScorer` return correct scores within `[0.0, 1.0]` for benign, critical, and border texts.
   - `test_dialogue_logging` checks that dialogue logs write properly to the database with scores.
4. **Drift Pipeline & Alerting (`A4`, `A7`)**:
   - `test_weekly_drift_pipeline_and_mlflow` executes the pipeline logic on a simulated week of data and verifies that standard drift and safety alert thresholds (Toxicity average `> 0.20`, Prompt Injection rate `> 5%`) log correctly to the DB and toggle warning statuses.
5. **MLflow Registry Tracking (`A5`)**:
   - `test_weekly_drift_pipeline_and_mlflow` verifies that the pipeline successfully contacts MLflow local registry and starts runs.
