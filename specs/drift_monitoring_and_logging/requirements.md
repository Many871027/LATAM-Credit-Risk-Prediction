# Analytical Requirements Specification — CR-004: Drift Monitoring and Logging

This document details the analytical requirements for the drift monitoring and logging system feature **CR-004 (drift_monitoring_and_logging)**.

## 📊 Business Acceptance Criteria Mapping
The business acceptance criteria defined in `feature_list.json` and requested extensions are mapped to the analytical requirements below:
- **Criterion 1 (PSI Calculation weekly):** Covered by **A1** (Weekly PSI Metric Calculation) and **A4** (Weekly Drift Pipeline Trigger).
- **Criterion 2 (Logging prediction inputs and outputs / telemetry):** Covered by **A2** (Prediction Log Ingestion) and **A6** (Missing/NULL Log Anomaly Handling).
- **Criterion 3 (MLflow Registry / Experiments Logging):** Covered by **A5** (MLflow Registry Tracking).
- **Criterion 4 (Evaluating LLM/safety drift using custom scorers):** Covered by **A3** (LLM Dialogue Safety Scoring) and **A7** (LLM Drift & Warning Threshold).

---

## 🔤 Analytical Requirements (EARS-BI Notation)

### 1. Ubiquitous (Base & Immutable Metrics)

*   **A1: Weekly PSI Metric Calculation**
    *   *Requirement*: The analytical layer SHALL calculate the Population Stability Index (PSI) weekly for prediction probabilities and model features using the sum of the difference between actual (production logs) and expected (training baseline) distribution proportions multiplied by the natural logarithm of their ratio.
    *   *Formulation*: 
        $$PSI = \sum_{i=1}^{k} \left( A_i - E_i \right) \times \ln\left( \frac{A_i}{E_i} \right)$$
        Where $A_i$ is the actual proportion in bin $i$, $E_i$ is the expected training proportion in bin $i$, and $k = 10$ (decile binning).
    *   *Grain*: Weekly metric per monitored variable.

*   **A2: Prediction Log Ingestion**
    *   *Requirement*: WHEN the inference service processes a prediction request, the system SHALL record the input features, outputs, latency, and status in the `gold.prediction_logs` table with idempotent write behavior.
    *   *Grain*: Single prediction event.

*   **A3: LLM Dialogue Safety Scoring**
    *   *Requirement*: The analytical layer SHALL calculate safety scores for dialogue logs (such as toxicity, prompt injection, and response fidelity) using custom scorers that evaluate text payloads and produce numerical scores between 0.0 and 1.0.
    *   *Grain*: Single dialogue interaction.

### 2. Event-Driven (ETL / Ingestion Strategies)

*   **A4: Weekly Drift Pipeline Trigger**
    *   *Requirement*: WHEN the weekly scheduled drift monitoring run occurs, the pipeline SHALL query the `gold.prediction_logs` and `gold.dialogue_logs` tables, compute the PSI for features and safety scores, and append the results to the `gold.drift_metrics` table with idempotent behavior.

*   **A5: MLflow Registry Tracking**
    *   *Requirement*: WHEN the weekly drift analysis runs, the pipeline SHALL process tracking information by logging the calculated PSI values, safety statistics, and drift alerts to the local MLflow server registry under the experiment `drift_monitoring_and_logging`.

### 3. Unwanted Behavior (Data Governance & Quality)

*   **A6: Missing/NULL Log Anomaly Handling**
    *   *Requirement*: IF any mandatory field in the prediction log request or response is missing or NULL, the system SHALL write the record to `gold.prediction_logs` with the `is_anomaly` flag set to true to isolate corruption.

### 4. State-Driven (AI Alerting Thresholds)

*   **A7: LLM Drift & Warning Threshold**
    *   *Requirement*: WHILE the weekly average toxicity score exceeds 0.20, or the prompt injection rate exceeds 5%, the system SHALL trigger an alert, flag the metric in the `gold.drift_metrics` table, and write a warning to the console/system logs.

---

## 📥 Input & Output Data Definitions

### Inputs
1.  **Production Prediction Logs**: Real-time payloads routed through `/predict` including `user_id`, `monthly_volume`, `session_regularity`, `income`, `probability_of_default`, `credit_limit`, `decision`, `latency_ms`, and `status`.
2.  **Production Dialogue Logs**: Real-time dialogue texts including `user_id`, `user_query`, and `bot_response`.
3.  **Baseline Distributions**: Feature and prediction distributions extracted from the training dataset (Gold layer `gold.target_construction` or training artifacts).

### Outputs
1.  **`gold.prediction_logs` Table**:
    *   `prediction_id` (VARCHAR/UUID): Primary key.
    *   `timestamp` (TIMESTAMP): Log insertion time.
    *   `user_id` (VARCHAR): User identifier.
    *   `monthly_volume` (DOUBLE): Input transaction volume.
    *   `session_regularity` (INTEGER): Input session days.
    *   `income` (DOUBLE): Input user income.
    *   `probability_of_default` (DOUBLE): Model prediction probability.
    *   `credit_limit` (DOUBLE): Allocated limit.
    *   `decision` (VARCHAR): Risk decision.
    *   `latency_ms` (DOUBLE): API response latency.
    *   `status` (VARCHAR): Request status (`SUCCESS` or `FALLBACK`).
    *   `is_anomaly` (BOOLEAN): Flag for corrupt/null fields.
2.  **`gold.dialogue_logs` Table**:
    *   `dialogue_id` (VARCHAR/UUID): Primary key.
    *   `timestamp` (TIMESTAMP): Event time.
    *   `user_id` (VARCHAR): User identifier.
    *   `user_query` (VARCHAR): User input prompt.
    *   `bot_response` (VARCHAR): LLM assistant response.
    *   `toxicity_score` (DOUBLE): Evaluated toxicity score [0-1].
    *   `prompt_injection_score` (DOUBLE): Evaluated injection probability [0-1].
    *   `fidelity_score` (DOUBLE): Evaluated response faithfulness [0-1].
3.  **`gold.drift_metrics` Table**:
    *   `metric_id` (VARCHAR/UUID): Primary key.
    *   `timestamp` (TIMESTAMP): Calculation time.
    *   `variable_name` (VARCHAR): Name of features, predictions, or safety scores.
    *   `psi_value` (DOUBLE): Computed PSI value.
    *   `drift_status` (VARCHAR): Drift category (`STABLE`, `MODERATE`, `DRIFT`).
    *   `alert_triggered` (BOOLEAN): Warning activation indicator.
