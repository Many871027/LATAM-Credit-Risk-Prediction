import os
import argparse
import sys
import logging
from src.models.train import train_pipeline, ModelValidationException

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RunTraining")

def main() -> None:
    parser = argparse.ArgumentParser(description="Run the XGBoost Credit Risk Model Training Pipeline.")
    parser.add_argument(
        "--db-path",
        type=str,
        default="credit_risk_medallion.db",
        help="Path to the DuckDB database file."
    )
    parser.add_argument(
        "--observation-date",
        type=str,
        default="2025-01-01",
        help="Observation cohort snapshot date (YYYY-MM-DD)."
    )
    parser.add_argument(
        "--model-output-path",
        type=str,
        default="models/trained_model",
        help="Path (base name without extension) to save the serialized model formats."
    )
    parser.add_argument(
        "--experiment-name",
        type=str,
        default="xgboost_model_training_pipeline",
        help="MLflow experiment name."
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed for reproducibility."
    )
    
    args = parser.parse_args()
    
    logger.info("Starting training run script...")
    logger.info(f"DB Path: {args.db_path}")
    logger.info(f"Observation Date: {args.observation_date}")
    logger.info(f"Model Output Path: {args.model_output_path}")
    logger.info(f"MLflow Experiment: {args.experiment_name}")
    
    try:
        metrics = train_pipeline(
            db_path=args.db_path,
            observation_date=args.observation_date,
            model_output_path=args.model_output_path,
            experiment_name=args.experiment_name,
            random_state=args.random_state
        )
        
        print("\n" + "=" * 50)
        print("          XGBOOST MODEL TRAINING SUMMARY")
        print("=" * 50)
        print("Model trained and validated successfully.")
        print(f"Metrics:")
        print(f"  - ROC-AUC:      {metrics['roc_auc']:.4f}")
        print(f"  - Gini Index:   {metrics['gini_index']:.4f} (Required: >= 0.65)")
        print(f"  - KS Statistic: {metrics['ks_statistic'] * 100:.2f}% (Required: >= 45.00%)")
        print(f"  - Accuracy:     {metrics['accuracy']:.4f}")
        print(f"  - Log Loss:     {metrics['log_loss']:.4f}")
        print("-" * 50)
        print(f"Model Artifacts Saved:")
        print(f"  - {args.model_output_path}.joblib (binary format)")
        print(f"  - {args.model_output_path}.skops (secure schema signature format)")
        print("=" * 50)
        
    except ModelValidationException as e:
        logger.error(f"Model training failed validation: {e}")
        sys.exit(2)
    except Exception as e:
        logger.error(f"Error during training pipeline: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
