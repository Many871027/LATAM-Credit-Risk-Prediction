"""
Population Stability Index (PSI) calculation and weekly drift analysis pipeline.
"""
import os
import uuid
import logging
import datetime
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
import duckdb
import skops.io as sio
import mlflow

from src.monitoring.logging_db import initialize_monitoring_db

logger = logging.getLogger("DriftMonitoring")

def calculate_psi(expected: np.ndarray, actual: np.ndarray, num_bins: int = 10) -> float:
    """
    Calculates the Population Stability Index (PSI) between two populations.
    
    Parameters:
        expected (np.ndarray): The baseline/reference population distribution (e.g. training data).
        actual (np.ndarray): The current/production population distribution.
        num_bins (int): Number of quantile bins to use. Default is 10 (deciles).
        
    Returns:
        float: Computed PSI value.
    """
    expected = np.array(expected)
    actual = np.array(actual)
    
    if len(expected) == 0 or len(actual) == 0:
        return 0.0
        
    # Calculate bin edges on expected using quantiles
    percentiles = np.linspace(0, 100, num_bins + 1)
    bin_edges = np.percentile(expected, percentiles)
    
    # Adjust duplicate bin edges if any (e.g. discrete features)
    unique_edges = np.unique(bin_edges)
    if len(unique_edges) < 2:
        bin_edges = np.array([bin_edges[0] - 1e-5, bin_edges[0] + 1e-5])
    else:
        bin_edges = unique_edges
        
    # Extend outer boundaries to cover all actual values
    extended_edges = bin_edges.copy()
    extended_edges[0] = -np.inf
    extended_edges[-1] = np.inf
    
    # Compute counts
    expected_counts, _ = np.histogram(expected, bins=extended_edges)
    actual_counts, _ = np.histogram(actual, bins=extended_edges)
    
    # Epsilon smoothing (1e-4) to prevent division by zero or log of zero
    epsilon = 1e-4
    expected_counts = np.maximum(expected_counts, epsilon)
    actual_counts = np.maximum(actual_counts, epsilon)
    
    # Convert counts to proportions
    expected_props = expected_counts / np.sum(expected_counts)
    actual_props = actual_counts / np.sum(actual_counts)
    
    # Calculate PSI
    psi_value = np.sum((actual_props - expected_props) * np.log(actual_props / expected_props))
    return float(psi_value)

def get_baseline_distributions(conn: duckdb.DuckDBPyConnection, model_path: Optional[str] = None) -> pd.DataFrame:
    """
    Queries baseline distributions from target_construction and computes predictions using the trained model.
    If no training data exists, returns simulated baseline data.
    """
    try:
        df_baseline = conn.execute("SELECT monthly_volume, session_regularity FROM gold.target_construction").df()
    except Exception as e:
        logger.warning(f"Could not read from gold.target_construction: {e}. Simulating baseline training distribution.")
        df_baseline = pd.DataFrame()
        
    if df_baseline.empty:
        # Fallback/simulation of baseline training data
        rng = np.random.RandomState(42)
        n = 1000
        df_baseline = pd.DataFrame({
            "monthly_volume": rng.exponential(scale=5000.0, size=n),
            "session_regularity": rng.randint(0, 31, size=n),
        })
        
    # Synthesize baseline income
    rng = np.random.RandomState(42)
    epsilon = rng.lognormal(mean=9.5, sigma=0.5, size=len(df_baseline))
    df_baseline['income'] = np.maximum(15000.0, 1.5 * df_baseline['monthly_volume'] + epsilon)
    
    # Attempt to load model
    model = None
    if model_path is None:
        model_path = os.getenv("MODEL_PATH", "models/trained_model.skops")
        
    if os.path.exists(model_path):
        try:
            model = sio.load(
                model_path,
                trusted=[
                    "xgboost.sklearn.XGBClassifier",
                    "xgboost.core.Booster",
                    "numpy.dtype",
                    "numpy.core.multiarray._reconstruct"
                ]
            )
        except Exception as e:
            logger.warning(f"Could not load model from {model_path}: {e}")
            
    # Check current directory for any fallback .skops model
    if model is None:
        for f in os.listdir("."):
            if f.endswith(".skops"):
                try:
                    model = sio.load(
                        f,
                        trusted=[
                            "xgboost.sklearn.XGBClassifier",
                            "xgboost.core.Booster",
                            "numpy.dtype",
                            "numpy.core.multiarray._reconstruct"
                        ]
                    )
                    logger.info(f"Loaded fallback model from {f}")
                    break
                except Exception:
                    pass
                    
    # If no model found, train a quick dummy model
    if model is None:
        logger.info("No model found. Training a quick dummy model on baseline data.")
        import xgboost as xgb
        # Create a dummy target
        y_dummy = (df_baseline["monthly_volume"] > 5000).astype(int)
        model = xgb.XGBClassifier(n_estimators=5, max_depth=2, random_state=42)
        model.fit(df_baseline[["monthly_volume", "session_regularity", "income"]], y_dummy)
        
    # Generate baseline default probabilities
    X = df_baseline[["monthly_volume", "session_regularity", "income"]]
    probs = model.predict_proba(X)[:, 1]
    df_baseline["probability_of_default"] = probs
    
    return df_baseline

def run_weekly_drift_analysis(db_path: str, reference_date: str) -> Dict[str, Any]:
    """
    Executes the weekly scheduled drift monitoring run.
    """
    # Initialize table schemas
    initialize_monitoring_db(db_path)
    
    conn = duckdb.connect(db_path)
    
    # Calculate datetime range (7 days preceding and including reference_date)
    ref_dt = datetime.datetime.strptime(reference_date, "%Y-%m-%d")
    start_dt = ref_dt - datetime.timedelta(days=7)
    
    start_str = start_dt.strftime("%Y-%m-%d 00:00:00")
    ref_str = ref_dt.strftime("%Y-%m-%d 23:59:59")
    
    logger.info(f"Running weekly drift analysis for date {reference_date} (Range: {start_str} to {ref_str})")
    
    try:
        # Retrieve production prediction logs
        df_pred = conn.execute(
            """
            SELECT monthly_volume, session_regularity, income, probability_of_default
            FROM gold.prediction_logs
            WHERE timestamp >= ? AND timestamp <= ?
            """,
            (start_str, ref_str)
        ).df()
        
        # Retrieve production dialogue logs
        df_dialogue = conn.execute(
            """
            SELECT toxicity_score, prompt_injection_score, fidelity_score
            FROM gold.dialogue_logs
            WHERE timestamp >= ? AND timestamp <= ?
            """,
            (start_str, ref_str)
        ).df()
        
        # Retrieve baseline training distributions
        df_baseline = get_baseline_distributions(conn)
        
    except Exception as e:
        logger.error(f"Error querying database for drift analysis: {e}")
        conn.close()
        raise e
        
    results = {
        "reference_date": reference_date,
        "start_date": start_str,
        "end_date": ref_str,
        "total_predictions": len(df_pred),
        "total_dialogues": len(df_dialogue),
        "metrics": {},
        "alerts_triggered": False
    }
    
    any_alert = False
    
    # 1. Compute PSI for prediction inputs and outputs
    variables = ["monthly_volume", "session_regularity", "income", "probability_of_default"]
    for var in variables:
        if df_pred.empty:
            psi_val = 0.0
            drift_status = "STABLE"
            alert_triggered = False
        else:
            expected_vals = df_baseline[var].values
            actual_vals = df_pred[var].dropna().values
            
            if len(actual_vals) == 0:
                psi_val = 0.0
                drift_status = "STABLE"
                alert_triggered = False
            else:
                psi_val = calculate_psi(expected_vals, actual_vals)
                if psi_val >= 0.25:
                    drift_status = "DRIFT"
                    alert_triggered = True
                elif psi_val >= 0.1:
                    drift_status = "MODERATE"
                    alert_triggered = False
                else:
                    drift_status = "STABLE"
                    alert_triggered = False
                    
        results["metrics"][var] = {
            "psi": psi_val,
            "status": drift_status,
            "alert": alert_triggered
        }
        if alert_triggered:
            any_alert = True
            
    # 2. Dialogue safety scorers average and threshold checks
    safety_vars = ["toxicity_score", "prompt_injection_score", "fidelity_score"]
    
    # Define a clean expected reference baseline for safety metrics
    safety_baselines = {
        "toxicity_score": np.zeros(100),
        "prompt_injection_score": np.zeros(100),
        "fidelity_score": np.ones(100)
    }
    
    for var in safety_vars:
        if df_dialogue.empty:
            psi_val = 0.0
            avg_val = 1.0 if var == "fidelity_score" else 0.0
            rate_val = 0.0
            drift_status = "STABLE"
            alert_triggered = False
        else:
            actual_vals = df_dialogue[var].dropna().values
            if len(actual_vals) == 0:
                psi_val = 0.0
                avg_val = 1.0 if var == "fidelity_score" else 0.0
                rate_val = 0.0
                drift_status = "STABLE"
                alert_triggered = False
            else:
                expected_vals = safety_baselines[var]
                psi_val = calculate_psi(expected_vals, actual_vals)
                avg_val = float(np.mean(actual_vals))
                
                # Injection rate is percentage of matches (>0)
                if var == "prompt_injection_score":
                    rate_val = float(np.mean(actual_vals > 0.0))
                else:
                    rate_val = 0.0
                    
                # PSI based drift status
                if psi_val >= 0.25:
                    drift_status = "DRIFT"
                    alert_triggered = True
                elif psi_val >= 0.1:
                    drift_status = "MODERATE"
                    alert_triggered = False
                else:
                    drift_status = "STABLE"
                    alert_triggered = False
                    
                # A7 logic: threshold checks overriding alerts
                if var == "toxicity_score" and avg_val > 0.20:
                    alert_triggered = True
                    logger.warning(f"[SAFETY ALERT] Toxicity average {avg_val:.4f} > 0.20!")
                elif var == "prompt_injection_score" and rate_val > 0.05:
                    alert_triggered = True
                    logger.warning(f"[SAFETY ALERT] Prompt injection rate {rate_val:.4f} > 5%!")
                    
        results["metrics"][var] = {
            "psi": psi_val,
            "avg": avg_val,
            "rate": rate_val,
            "status": drift_status,
            "alert": alert_triggered
        }
        if alert_triggered:
            any_alert = True
            
    results["alerts_triggered"] = any_alert
    
    # 3. Store metrics in DuckDB gold.drift_metrics with idempotency
    try:
        # Delete existing entries for this reference_date (or timestamp) to enforce idempotency
        conn.execute("DELETE FROM gold.drift_metrics WHERE CAST(timestamp AS DATE) = CAST(? AS DATE)", (reference_date,))
        
        for var, m in results["metrics"].items():
            metric_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO gold.drift_metrics (
                    metric_id, timestamp, variable_name, psi_value, drift_status, alert_triggered
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (metric_id, reference_date, var, m["psi"], m["status"], m["alert"])
            )
        logger.info(f"Drift metrics saved to database.")
    except Exception as e:
        logger.error(f"Failed to save drift metrics to DB: {e}")
        conn.close()
        raise e
    finally:
        conn.close()
        
    # 4. Log to local MLflow server
    try:
        mlflow.set_experiment("drift_monitoring_and_logging")
        with mlflow.start_run(run_name=f"drift_analysis_{reference_date}"):
            # Log Parameters
            mlflow.log_param("reference_date", reference_date)
            mlflow.log_param("start_date", start_str)
            mlflow.log_param("end_date", ref_str)
            mlflow.log_param("total_predictions_evaluated", len(df_pred))
            mlflow.log_param("total_dialogues_evaluated", len(df_dialogue))
            
            # Log Metrics
            for var, m in results["metrics"].items():
                mlflow.log_metric(f"psi_{var}", m["psi"])
                mlflow.log_metric(f"alert_{var}", 1 if m["alert"] else 0)
                if var == "probability_of_default":
                    mlflow.log_metric("drift_alert_probability_of_default", 1 if m["psi"] >= 0.25 else 0)
                if "avg" in m:
                    mlflow.log_metric(f"avg_{var}", m["avg"])
                if "rate" in m and var == "prompt_injection_score":
                    mlflow.log_metric("rate_prompt_injection", m["rate"])
                    
            logger.info("Drift monitoring metrics logged to MLflow successfully.")
    except Exception as e:
        logger.warning(f"Could not log to MLflow: {e}")
        
    return results
