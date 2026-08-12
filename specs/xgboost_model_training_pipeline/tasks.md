# Implementation Tasks Checklist — CR-002: XGBoost Model Training Pipeline

This document lists the step-by-step implementation tasks required to build the model training pipeline using XGBoost, scikit-learn, joblib, skops, and MLflow tracking.

---

## 📋 Tasks Checklist

### Phase 1: Environment & Directory Initialization

- [x] **Task 1: Setup Dependencies and Directory Structure**
      Create the `src/models` directory if it does not exist. Ensure that `xgboost`, `scikit-learn`, `mlflow`, `joblib`, and `skops` are declared in the project's dependency config (e.g. `requirements.txt`) and installed in the virtual environment. Define empty Python files `src/models/train.py`, `src/models/metrics.py`, and `src/models/registry.py`.
      *Requirement Mapping:* None (Infrastructure / Environment Setup)

### Phase 2: Feature Engineering & Data Preparation

- [x] **Task 2: Implement Data Loading and Synthetic Feature Engineering**
      Write a function `load_training_data(db_path: str, observation_date: str)` that connects to DuckDB and executes a query extracting `monthly_volume`, `session_regularity`, and the target `target_default_30d` from the `gold.target_construction` table. Synthesize/impute an `income` feature for each user correlating with their `monthly_volume` (e.g. following a log-normal distribution or a scaling factor plus noise) and return a unified pandas DataFrame.
      *Requirement Mapping:* `A3`

- [x] **Task 3: Implement Imputation & Partitioning Split**
      Write preprocessing functions that check for missing/infinite values and replace them with median values calculated strictly from the training partition to prevent data leakage. Partition the dataset into a 70% training split and a 30% testing split, stratified by the `target_default_30d` column to maintain target distribution.
      *Requirement Mapping:* `A3`, `A7`

### Phase 3: Model Training & Evaluation Metrics

- [x] **Task 4: Implement Training with Imbalance Scaling**
      Configure `xgboost.XGBClassifier` using the designed hyperparameters (`n_estimators=100`, `max_depth=5`, `learning_rate=0.05`, `subsample=0.8`, `colsample_bytree=0.8`, `objective='binary:logistic'`). Calculate the `scale_pos_weight` hyperparameter dynamically as the ratio of non-defaults to defaults in the training partition, and fit the model.
      *Requirement Mapping:* `A3`

- [x] **Task 5: Implement Gini and KS Metrics Calculation**
      Write metric evaluation helper functions in `src/models/metrics.py` to calculate:
      1. Area Under the ROC Curve (ROC-AUC).
      2. Gini Index using the formula `2 * ROC_AUC - 1`.
      3. Kolmogorov-Smirnov (KS) statistic by comparing the maximum difference between cumulative distributions of prediction probabilities for default vs. non-default classes.
      *Requirement Mapping:* `A1`, `A2`

### Phase 4: Validation Gate, MLflow Logging & Serialization

- [x] **Task 6: Implement Model Validation Gate**
      Write a validation check that runs after model evaluation. If the Gini index on the test partition is less than 0.65 or the KS statistic is less than 45%, raise a `ModelValidationException` and halt the execution.
      *Requirement Mapping:* `A4`

- [x] **Task 7: Implement MLflow Logging Integration**
      Instrument the training pipeline block in `src/models/train.py` with MLflow tracking. Set the active experiment, start an MLflow run, log all hyperparameters (including `scale_pos_weight`), log training/validation evaluation metrics, and log the final serialized model run artifact.
      *Requirement Mapping:* `A6`

- [x] **Task 8: Implement Safe Serialization with Joblib and Skops**
      Write a utility function to serialize the validated model using `joblib` and extract its schema signature using `skops.io.dump()` to a production-ready path.
      *Requirement Mapping:* `A5`

### Phase 5: Verification & Integration Tests

- [x] **Task 9: Implement Automated Test Suite**
      Create a test file `tests/test_model_training.py`. Implement unit tests verifying:
      1. Standard training data extraction and synthetic income column generation.
      2. Stratified train/test splitting functionality and median feature imputation rules.
      3. Mathematical accuracy of Gini and KS calculations on mock prediction distributions.
      4. Correct behavior of the Validation Gate (raising exceptions when thresholds are violated).
      5. Correct serialization of the model using joblib and skops metadata.
      Run all tests using `./init.sh` and ensure 100% green status.
      *Requirement Mapping:* `A1` to `A7`

### Phase 6: Unified Pipeline Execution

- [x] **Task 10: Create Unified Training Execution Script**
      Create a single, unified Python script `src/models/run_training.py` that aggregates and executes all operations, queries, and report generation procedures defined in the preceding tasks of this specification (i.e. loading raw features, performing pre-processing, training the model, evaluating and validating metrics, saving the serialized model, logging to MLflow, and printing a report summarizing model metrics).
      *Requirement Mapping:* All (`A1` - `A7`)
