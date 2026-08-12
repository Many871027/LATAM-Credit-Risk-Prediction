import os
import logging
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pandas as pd
import duckdb
from sklearn.model_selection import train_test_split
import xgboost as xgb
import mlflow
import mlflow.xgboost

from src.models.metrics import (
    calculate_roc_auc,
    calculate_gini,
    calculate_ks,
    calculate_accuracy,
    calculate_log_loss
)
from src.models.registry import save_model

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ModelTrainingPipeline")

class ModelValidationException(Exception):
    """Custom exception raised when model performance does not meet acceptance criteria."""
    pass

def load_training_data(db_path: str, observation_date: str, seed: int = 42) -> pd.DataFrame:
    """Connects to DuckDB and extracts model training features.
    
    Synthesizes an income feature correlating with monthly_volume.
    
    Args:
        db_path: Path to the DuckDB database.
        observation_date: The cohort observation date.
        seed: Random seed for generating synthetic income.
        
    Returns:
        pd.DataFrame: DataFrame containing training features and targets.
    """
    logger.info(f"Loading training data from DuckDB at {db_path} for date {observation_date}")
    
    conn = duckdb.connect(db_path)
    try:
        # Check if table exists
        query = """
        SELECT user_id, monthly_volume, session_regularity, target_default_30d
        FROM gold.target_construction
        WHERE CAST(observation_date AS VARCHAR) = ?
        """
        df = conn.execute(query, [observation_date]).df()
    except Exception as e:
        logger.error(f"Error loading training data: {e}")
        raise e
    finally:
        conn.close()
        
    if df.empty:
        logger.warning(f"No records found for observation date {observation_date}")
        return pd.DataFrame(columns=["user_id", "monthly_volume", "session_regularity", "target_default_30d", "income"])
        
    # Generate synthetic income:
    # income_u = max(15000, 1.5 * monthly_volume + epsilon) where epsilon ~ LN(mean=9.5, sigma=0.5)
    rng = np.random.RandomState(seed)
    epsilon = rng.lognormal(mean=9.5, sigma=0.5, size=len(df))
    df['income'] = np.maximum(15000.0, 1.5 * df['monthly_volume'] + epsilon)
    
    return df

def split_and_impute_data(
    df: pd.DataFrame,
    feature_cols: List[str],
    target_col: str,
    test_size: float = 0.3,
    random_state: int = 42
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Applies value bounds, splits data into train/test, and imputes missing/infinite values.
    
    Args:
        df: Input DataFrame containing features and target.
        feature_cols: List of feature column names.
        target_col: Target column name.
        test_size: Proportion of test split.
        random_state: Seed for reproducibility.
        
    Returns:
        Tuple containing:
            - X_train: Preprocessed train features.
            - X_test: Preprocessed test features.
            - y_train: Train targets.
            - y_test: Test targets.
    """
    logger.info("Applying feature bound containment and data partitioning...")
    df_clean = df.copy()
    
    # 1. Feature Value Bound Containment
    if 'monthly_volume' in df_clean.columns:
        df_clean['monthly_volume'] = np.where(df_clean['monthly_volume'] < 0, 0.0, df_clean['monthly_volume'])
    if 'session_regularity' in df_clean.columns:
        df_clean['session_regularity'] = np.where(df_clean['session_regularity'] < 0, 0, df_clean['session_regularity'])
        df_clean['session_regularity'] = np.where(df_clean['session_regularity'] > 30, 30, df_clean['session_regularity'])
    if 'income' in df_clean.columns:
        # If income < 0 or NULL, it will be set to NaN so that it is imputed with training median
        df_clean['income'] = np.where(df_clean['income'] < 0, np.nan, df_clean['income'])
        
    X = df_clean[feature_cols].copy()
    y = df_clean[target_col].copy()
    
    # Stratified split to maintain target class distribution
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=test_size,
        random_state=random_state,
        stratify=y
    )
    
    # 2. Missing and Infinity Values Imputation (A7)
    # Replace infinities with NaN in train and test
    X_train = X_train.replace([np.inf, -np.inf], np.nan)
    X_test = X_test.replace([np.inf, -np.inf], np.nan)
    
    # Calculate median strictly from the training set
    medians = X_train.median()
    # Back up fillna for columns that are all NaN in train
    medians = medians.fillna(0.0)
    
    # Impute missing values
    X_train = X_train.fillna(medians)
    X_test = X_test.fillna(medians)
    
    return X_train, X_test, y_train, y_test

def train_pipeline(
    db_path: str,
    observation_date: str,
    model_output_path: str,
    experiment_name: str = "xgboost_model_training_pipeline",
    random_state: int = 42
) -> Dict[str, Any]:
    """Runs the entire training pipeline, including MLflow logging and model registration.
    
    Args:
        db_path: Path to the DuckDB database.
        observation_date: Cohort date to extract.
        model_output_path: Path (base filename) to save the serialized model formats.
        experiment_name: Name of the MLflow experiment.
        random_state: Random seed for train/test split and XGBoost model.
        
    Returns:
        Dict: Dictionary containing evaluation metrics.
    """
    logger.info("Starting model training pipeline...")
    
    # 1. Load data
    df = load_training_data(db_path, observation_date, seed=random_state)
    if df.empty:
        raise ValueError(f"No data loaded for observation date: {observation_date}")
    if len(df) < 10:
        raise ValueError("Insufficient data to train the model. Must have at least 10 records.")
        
    feature_cols = ["monthly_volume", "session_regularity", "income"]
    target_col = "target_default_30d"
    
    # Check if we have positive and negative classes
    if df[target_col].nunique() < 2:
        raise ValueError("Target default class must contain both 0 and 1 for model training.")
        
    # 2. Partition & Preprocess
    X_train, X_test, y_train, y_test = split_and_impute_data(
        df, feature_cols, target_col, test_size=0.3, random_state=random_state
    )
    
    # 3. Calculate scale_pos_weight
    num_defaults = np.sum(y_train == 1)
    num_non_defaults = np.sum(y_train == 0)
    if num_defaults > 0:
        scale_pos_weight = float(num_non_defaults) / float(num_defaults)
    else:
        scale_pos_weight = 1.0
        
    # 4. Configure & Train XGBClassifier
    params = {
        "n_estimators": 100,
        "max_depth": 5,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "objective": "binary:logistic",
        "eval_metric": "logloss",
        "scale_pos_weight": scale_pos_weight,
        "random_state": random_state
    }
    
    model = xgb.XGBClassifier(**params)
    model.fit(X_train, y_train)
    
    # 5. Evaluate on Test Split
    y_prob = model.predict_proba(X_test)[:, 1]
    y_pred = model.predict(X_test)
    
    roc_auc = calculate_roc_auc(y_test, y_prob)
    gini = calculate_gini(y_test, y_prob)
    ks = calculate_ks(y_test, y_prob)
    accuracy = calculate_accuracy(y_test, y_pred)
    loss = calculate_log_loss(y_test, y_prob)
    
    metrics = {
        "roc_auc": roc_auc,
        "gini_index": gini,
        "ks_statistic": ks,
        "accuracy": accuracy,
        "log_loss": loss
    }
    
    logger.info(f"Evaluation Metrics: {metrics}")
    
    # 6. Performance Validation Gate (A4)
    # Gini >= 0.65 and KS >= 45% (0.45)
    if gini < 0.65 or ks < 0.45:
        raise ModelValidationException(
            f"Performance validation gate failed. "
            f"Required: Gini >= 0.65, KS >= 45% (0.45). "
            f"Got: Gini = {gini:.4f}, KS = {ks:.4f}."
        )
        
    logger.info("Performance validation gate passed successfully.")
    
    # 7. MLflow Logging (A6)
    mlflow.set_experiment(experiment_name)
    with mlflow.start_run() as run:
        # Log parameters
        mlflow.log_params(params)
        
        # Log metrics
        mlflow.log_metrics(metrics)
        
        # Log model artifact (XGBoost)
        mlflow.xgboost.log_model(model, "model")
        
        logger.info(f"MLflow run logged. Run ID: {run.info.run_id}")
        
    # 8. Safe Serialization using Joblib and Skops (A5)
    save_model(model, model_output_path)
    logger.info(f"Model successfully saved to {model_output_path}.joblib/skops")
    
    return metrics
