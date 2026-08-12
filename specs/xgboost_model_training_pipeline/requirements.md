# Analytical Requirements Specification — CR-002: XGBoost Model Training Pipeline

This document details the analytical requirements for the credit risk model training feature **CR-002 (xgboost_model_training_pipeline)**.

## 📊 Business Acceptance Criteria Mapping
The business acceptance criteria defined in `feature_list.json` are mapped to the analytical requirements below:
- **Criterion 1 (Train XGBoost Classifier):** Covered by **A3** (Stratified Split Ingestion) and **A7** (Anomaly Imputation).
- **Criterion 2 (Validation Metrics & Thresholds):** Covered by **A1** (Gini Calculation), **A2** (KS Calculation), and **A4** (Validation Gate Alerting).
- **Criterion 3 (Model Serialization & Registry):** Covered by **A5** (Joblib & Skops Serialization) and **A6** (MLflow Logging Integration).

---

## 🔤 Analytical Requirements (EARS-BI Notation)

### 1. Ubiquitous (Base & Immutable Metrics)

*   **A1: Gini Index Metric Calculation**
    *   *Requirement*: The analytical layer SHALL calculate the Gini index using the formula `2 * ROC_AUC - 1` based on actual default targets and model prediction probabilities, yielding a single model evaluation metric.
    *   *Grain*: Model Run level

*   **A2: Kolmogorov-Smirnov (KS) Statistic Calculation**
    *   *Requirement*: The analytical layer SHALL calculate the KS statistic using the maximum vertical separation between the cumulative distribution functions of default and non-default classes over the model prediction probabilities.
    *   *Grain*: Model Run level

### 2. Event-Driven (ETL / Ingestion Strategies)

*   **A3: Stratified Split Ingestion**
    *   *Requirement*: WHEN the model training pipeline is executed, the pipeline SHALL process the input Gold target construction table and Silver users table into a 70% training split and a 30% testing split with stratified target default behavior.

*   **A5: Model Serialization & Registration**
    *   *Requirement*: WHEN model validation succeeds, the pipeline SHALL process the serialization and registration of the trained XGBoost model using joblib and skops to the target storage path.

*   **A6: MLflow Experiment Tracking**
    *   *Requirement*: WHEN a model training run executes, the pipeline SHALL process tracking information by logging parameters, metrics, and artifact files to the local MLflow server with idempotent run execution behavior.

### 3. Unwanted Behavior (Data Governance & Quality)

*   **A7: Feature Anomaly Imputation**
    *   *Requirement*: IF missing values, NaNs, or infinities are detected in the training features, the system SHALL impute them using median values computed from the training split to prevent training errors.

### 4. State-Driven (AI Alerting Thresholds)

*   **A4: Model Performance Validation Gate**
    *   *Requirement*: WHILE the validation Gini index is less than 0.65 or the validation KS statistic is less than 45%, the validation system SHALL raise a ModelValidationException, halt pipeline execution, and abort the model registration workflow.

---

## 📥 Input & Output Data Definitions

### Inputs
1.  **DuckDB Layer Data sources**:
    - `gold.target_construction`: Contains `user_id`, `observation_date`, `monthly_volume`, `session_regularity`, and the target label `target_default_30d`.
    - `silver.users` (or synthetic source): To retrieve user demographic metadata (e.g. `income` features). If `income` is not yet available in the database, the ingestion task must synthesize a realistic income feature correlating with user volume.

### Outputs
1.  **Serialized Model Artifacts**:
    - `model.joblib`: Binary serialization of the trained XGBoost model.
    - `model.skops`: Model signature and metadata format file for secure loading.
2.  **MLflow Local Runs**:
    - Experiment runs tracking parameters, curves, and artifacts.
