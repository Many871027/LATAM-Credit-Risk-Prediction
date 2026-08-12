import os
import logging
import sqlite3
from typing import Dict, Any, List, Optional, Tuple

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TargetConstructionPipeline")

QUERIES_DIR = os.path.join(os.path.dirname(__file__), "queries")

def load_sql_query(query_name: str) -> str:
    """Loads a SQL template from the queries directory."""
    file_path = os.path.join(QUERIES_DIR, f"{query_name}.sql")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"SQL template not found at {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def run_audit(db_conn: Any, use_sqlite: bool = False) -> Dict[str, int]:
    """Executes the data quality audit and returns anomaly counts."""
    logger.info("Executing database quality audit...")
    raw_sql = load_sql_query("audit_data")
    
    if use_sqlite:
        from tests.mock_db_harness import translate_bq_to_sqlite
        sql = translate_bq_to_sqlite(raw_sql)
        cursor = db_conn.cursor()
        cursor.execute(sql)
        row = cursor.fetchone()
        columns = [col[0] for col in cursor.description]
        anomalies = dict(zip(columns, row))
    else:
        # BigQuery execution
        query_job = db_conn.query(raw_sql)
        result = query_job.result()
        row = list(result)[0]
        anomalies = {k: v for k, v in row.items()}
        
    for k, v in anomalies.items():
        if v > 0:
            logger.warning(f"Data Quality Anomaly detected: {k} = {v} rows discarded or marked invalid.")
            
    return anomalies

def extract_features(db_conn: Any, observation_date: str, use_sqlite: bool = False) -> List[Dict[str, Any]]:
    """Calculates user monthly volume and session regularity for an observation date."""
    logger.info(f"Extracting user features for observation date: {observation_date}")
    raw_sql = load_sql_query("extract_features")
    
    if use_sqlite:
        from tests.mock_db_harness import translate_bq_to_sqlite
        sql = translate_bq_to_sqlite(raw_sql)
        cursor = db_conn.cursor()
        cursor.execute(sql, {"observation_date": observation_date})
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    else:
        # BigQuery execution
        from google.cloud import bigquery
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("observation_date", "DATE", observation_date)
            ]
        )
        query_job = db_conn.query(raw_sql, job_config=job_config)
        return [dict(row) for row in query_job.result()]

def build_target(db_conn: Any, observation_date: str, use_sqlite: bool = False) -> List[Dict[str, Any]]:
    """Calculates DPD30 targets within a 12-month window from the observation date."""
    logger.info(f"Building default targets for observation date: {observation_date}")
    raw_sql = load_sql_query("build_target")
    
    if use_sqlite:
        from tests.mock_db_harness import translate_bq_to_sqlite
        sql = translate_bq_to_sqlite(raw_sql)
        cursor = db_conn.cursor()
        cursor.execute(sql, {"observation_date": observation_date})
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    else:
        # BigQuery execution
        from google.cloud import bigquery
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("observation_date", "DATE", observation_date)
            ]
        )
        query_job = db_conn.query(raw_sql, job_config=job_config)
        return [dict(row) for row in query_job.result()]

def ingest_cohort_data(
    db_conn: Any, 
    observation_date: str, 
    records: List[Dict[str, Any]], 
    use_sqlite: bool = False
) -> None:
    """Idempotently merges cohort records into target_construction table."""
    logger.info(f"Ingesting {len(records)} cohort records for {observation_date}...")
    if not records:
        logger.warning("No records to ingest.")
        return

    raw_sql = load_sql_query("merge_target_construction")

    if use_sqlite:
        from tests.mock_db_harness import translate_bq_to_sqlite
        sql = translate_bq_to_sqlite(raw_sql)
        cursor = db_conn.cursor()
        
        # Stage data into temporary staging table
        cursor.execute("DROP TABLE IF EXISTS staged_target_construction;")
        cursor.execute("""
            CREATE TABLE staged_target_construction (
              user_id TEXT,
              observation_date TEXT,
              monthly_volume REAL,
              session_regularity INTEGER,
              target_default_30d INTEGER
            );
        """)
        
        insert_tuples = [
            (
                r["user_id"],
                r["observation_date"],
                float(r["monthly_volume"]),
                int(r["session_regularity"]),
                int(r["target_default_30d"])
            )
            for r in records
        ]
        cursor.executemany(
            "INSERT INTO staged_target_construction VALUES (?, ?, ?, ?, ?);",
            insert_tuples
        )
        
        # Perform merge equivalent
        cursor.execute(sql)
        db_conn.commit()
        logger.info("Idempotent merge completed in SQLite.")
    else:
        # BigQuery execution
        from google.cloud import bigquery
        # Setup staging table
        staged_table_id = "credit_risk.staged_target_construction"
        
        # Schema definition matching staged table
        schema = [
            bigquery.SchemaField("user_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("observation_date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("monthly_volume", "NUMERIC", mode="REQUIRED"),
            bigquery.SchemaField("session_regularity", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("target_default_30d", "INTEGER", mode="REQUIRED"),
        ]
        
        job_config = bigquery.LoadJobConfig(
            schema=schema,
            write_disposition="WRITE_TRUNCATE",
        )
        
        # Convert numeric and types safely for BQ loading
        formatted_records = []
        for r in records:
            formatted_records.append({
                "user_id": r["user_id"],
                "observation_date": str(r["observation_date"]),
                "monthly_volume": float(r["monthly_volume"]),
                "session_regularity": int(r["session_regularity"]),
                "target_default_30d": int(r["target_default_30d"])
            })
            
        load_job = db_conn.load_table_from_json(
            formatted_records,
            staged_table_id,
            job_config=job_config
        )
        load_job.result() # Wait for loading to finish
        
        # Merge staged table to target table
        query_job = db_conn.query(raw_sql)
        query_job.result()
        logger.info("Idempotent merge completed in BigQuery.")

def check_cohort_alerts(
    db_conn: Any, 
    observation_date: str, 
    use_sqlite: bool = False
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Monitors the average cohort default rate grouped by registration month.
    Triggers an alert warning if any registration cohort exceeds 15% default rate."""
    
    # We query the target_construction joined with raw.users to group by registration month
    raw_query = """
    WITH cohort_targets AS (
      SELECT user_id, target_default_30d
      FROM credit_risk.target_construction
      WHERE observation_date = @observation_date
    ),
    deduplicated_users AS (
      SELECT user_id, created_at
      FROM (
        SELECT 
          user_id,
          created_at,
          ROW_NUMBER() OVER (
            PARTITION BY user_id 
            ORDER BY updated_at DESC, ingestion_timestamp DESC
          ) as row_num
        FROM raw.users
        WHERE user_id IS NOT NULL
      )
      WHERE row_num = 1
    )
    SELECT 
      SUBSTR(SAFE_CAST(u.created_at AS STRING), 1, 7) AS reg_month,
      AVG(CAST(c.target_default_30d AS REAL)) AS default_rate,
      COUNT(*) AS cohort_size
    FROM cohort_targets c
    JOIN deduplicated_users u ON c.user_id = u.user_id
    GROUP BY reg_month;
    """
    
    if use_sqlite:
        from tests.mock_db_harness import translate_bq_to_sqlite
        sql = translate_bq_to_sqlite(raw_query)
        cursor = db_conn.cursor()
        cursor.execute(sql, {"observation_date": observation_date})
        columns = [col[0] for col in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
    else:
        from google.cloud import bigquery
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("observation_date", "DATE", observation_date)
            ]
        )
        query_job = db_conn.query(raw_query, job_config=job_config)
        results = [dict(row) for row in query_job.result()]
        
    alerts = []
    for row in results:
        rate = row["default_rate"]
        reg_month = row["reg_month"]
        size = row["cohort_size"]
        if rate > 0.15:
            logger.warning(
                f"[ALERT] Quality warning: Registration cohort '{reg_month}' "
                f"exceeded 15% default threshold! (Rate: {rate:.2%}, Cohort Size: {size})"
            )
            alerts.append(row)
            
    drift_report = None
    if alerts:
        drift_report = f"# Diagnostic Drift Report — Cohort {observation_date}\n\n"
        drift_report += f"Generated for observation cohort date: {observation_date}\n"
        drift_report += "Status: WARNING — High Default Rate Alert Triggered\n\n"
        drift_report += "Potential shift in credit profile or adverse selection detected in the following cohorts:\n"
        for alert in alerts:
            drift_report += (
                f"- **Registration Month**: {alert['reg_month']} | "
                f"**Default Rate**: {alert['default_rate']:.2f}% | "
                f"**Cohort Size**: {alert['cohort_size']} users\n"
            )
            
    return results, drift_report

def run_target_construction_pipeline(
    db_conn: Any, 
    observation_date: str, 
    use_sqlite: bool = False
) -> Dict[str, Any]:
    """Runs the entire target construction pipeline for a cohort observation date."""
    logger.info(f"Starting target construction pipeline for cohort date: {observation_date}")
    
    # 1. Run audit logs
    audit_results = run_audit(db_conn, use_sqlite=use_sqlite)
    
    # 2. Extract features
    features = extract_features(db_conn, observation_date, use_sqlite=use_sqlite)
    
    # 3. Build target
    targets = build_target(db_conn, observation_date, use_sqlite=use_sqlite)
    
    # 4. Combine in memory
    combined = {}
    for row in features:
        uid = row["user_id"]
        combined[uid] = {
            "user_id": uid,
            "observation_date": row["observation_date"],
            "monthly_volume": float(row["monthly_volume"]),
            "session_regularity": int(row["session_regularity"]),
            "target_default_30d": 0
        }
        
    for row in targets:
        uid = row["user_id"]
        if uid in combined:
            combined[uid]["target_default_30d"] = int(row["target_default_30d"])
        else:
            combined[uid] = {
                "user_id": uid,
                "observation_date": row["observation_date"],
                "monthly_volume": 0.0,
                "session_regularity": 0,
                "target_default_30d": int(row["target_default_30d"])
            }
            
    cohort_records = list(combined.values())
    
    # 5. Ingest/Merge cohort data
    ingest_cohort_data(db_conn, observation_date, cohort_records, use_sqlite=use_sqlite)
    
    # 6. Check cohort alerts and drift
    cohort_rates, drift_report = check_cohort_alerts(db_conn, observation_date, use_sqlite=use_sqlite)
    
    logger.info("Pipeline execution successfully completed.")
    return {
        "audit": audit_results,
        "record_count": len(cohort_records),
        "cohort_rates": cohort_rates,
        "drift_report": drift_report
    }
