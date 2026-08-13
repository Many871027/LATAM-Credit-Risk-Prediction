"""
Database logging utilities for prediction telemetry and dialogue logs in DuckDB.
"""
import duckdb
import logging
from typing import Optional

logger = logging.getLogger("LoggingDB")

def initialize_monitoring_db(db_path: str) -> None:
    """
    Initializes the monitoring tables under the gold schema in DuckDB.
    Creates gold schema if it does not exist.
    """
    logger.info(f"Initializing monitoring database tables at: {db_path}")
    conn = duckdb.connect(db_path)
    try:
        conn.execute("CREATE SCHEMA IF NOT EXISTS gold;")
        
        # 1. gold.prediction_logs
        conn.execute("""
        CREATE TABLE IF NOT EXISTS gold.prediction_logs (
            prediction_id VARCHAR PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id VARCHAR NOT NULL,
            monthly_volume DOUBLE,
            session_regularity INTEGER,
            income DOUBLE,
            probability_of_default DOUBLE,
            credit_limit DOUBLE,
            decision VARCHAR,
            latency_ms DOUBLE,
            status VARCHAR,
            is_anomaly BOOLEAN DEFAULT FALSE
        );
        """)
        
        # 2. gold.dialogue_logs
        conn.execute("""
        CREATE TABLE IF NOT EXISTS gold.dialogue_logs (
            dialogue_id VARCHAR PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id VARCHAR NOT NULL,
            user_query VARCHAR,
            bot_response VARCHAR,
            toxicity_score DOUBLE,
            prompt_injection_score DOUBLE,
            fidelity_score DOUBLE
        );
        """)
        
        # 3. gold.drift_metrics
        conn.execute("""
        CREATE TABLE IF NOT EXISTS gold.drift_metrics (
            metric_id VARCHAR PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            variable_name VARCHAR NOT NULL,
            psi_value DOUBLE NOT NULL,
            drift_status VARCHAR NOT NULL,
            alert_triggered BOOLEAN DEFAULT FALSE
        );
        """)
        logger.info("Monitoring tables initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize monitoring tables: {e}")
        raise e
    finally:
        conn.close()

def log_prediction(
    db_path: str,
    prediction_id: str,
    user_id: Optional[str],
    monthly_volume: Optional[float],
    session_regularity: Optional[int],
    income: Optional[float],
    probability_of_default: Optional[float],
    credit_limit: Optional[float],
    decision: Optional[str],
    latency_ms: Optional[float],
    status: Optional[str],
    is_anomaly: Optional[bool] = None
) -> None:
    """
    Logs a single prediction event to gold.prediction_logs.
    If any mandatory field is missing or NULL, is_anomaly will be set to True.
    """
    # Verify mandatory fields
    mandatory_fields = [
        prediction_id, user_id, monthly_volume, session_regularity,
        income, probability_of_default, credit_limit, decision,
        latency_ms, status
    ]
    
    if is_anomaly is None:
        is_anomaly = any(v is None for v in mandatory_fields)
    
    conn = duckdb.connect(db_path)
    try:
        # Use an INSERT query with standard placeholders or parameterized query
        # Since user_id could be None if corrupt, but SQL table says NOT NULL,
        # we provide a fallback for user_id to avoid SQL insert failures,
        # or we handle insertion failure.
        # Let's set user_id to 'UNKNOWN' if it is None, and set is_anomaly = True.
        clean_user_id = user_id if user_id is not None else "UNKNOWN"
        
        conn.execute(
            """
            INSERT INTO gold.prediction_logs (
                prediction_id, user_id, monthly_volume, session_regularity,
                income, probability_of_default, credit_limit, decision,
                latency_ms, status, is_anomaly
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                prediction_id, clean_user_id, monthly_volume, session_regularity,
                income, probability_of_default, credit_limit, decision,
                latency_ms, status, is_anomaly
            )
        )
    except Exception as e:
        logger.error(f"Error logging prediction: {e}")
        raise e
    finally:
        conn.close()

def log_dialogue(
    db_path: str,
    dialogue_id: str,
    user_id: Optional[str],
    user_query: Optional[str],
    bot_response: Optional[str],
    toxicity_score: float,
    prompt_injection_score: float,
    fidelity_score: float
) -> None:
    """
    Logs a single dialogue event to gold.dialogue_logs.
    """
    conn = duckdb.connect(db_path)
    try:
        clean_user_id = user_id if user_id is not None else "UNKNOWN"
        conn.execute(
            """
            INSERT INTO gold.dialogue_logs (
                dialogue_id, user_id, user_query, bot_response,
                toxicity_score, prompt_injection_score, fidelity_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                dialogue_id, clean_user_id, user_query, bot_response,
                toxicity_score, prompt_injection_score, fidelity_score
            )
        )
    except Exception as e:
        logger.error(f"Error logging dialogue: {e}")
        raise e
    finally:
        conn.close()
