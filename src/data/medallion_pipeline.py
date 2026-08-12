import os
import json
import logging
import duckdb
from typing import Dict, Any, List, Optional, Tuple, Union
from prefect import task, flow

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MedallionPipeline")

QUERIES_DIR = os.path.join(os.path.dirname(__file__), "queries")

def load_sql_query(query_name: str) -> str:
    """Loads a SQL template from the queries directory."""
    file_path = os.path.join(QUERIES_DIR, f"{query_name}.sql")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"SQL template not found at {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def initialize_duckdb_schemas(db_path: str) -> None:
    """Initializes the bronze, silver, and gold schemas and tables in DuckDB."""
    logger.info(f"Initializing DuckDB database schemas at: {db_path}")
    conn = duckdb.connect(db_path)
    try:
        conn.execute("CREATE SCHEMA IF NOT EXISTS bronze;")
        conn.execute("CREATE SCHEMA IF NOT EXISTS silver;")
        conn.execute("CREATE SCHEMA IF NOT EXISTS gold;")
        
        # Bronze Tables (all VARCHAR/TEXT to prevent load failures)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS bronze.users (
            user_id VARCHAR,
            created_at VARCHAR,
            country VARCHAR,
            updated_at VARCHAR,
            ingestion_timestamp VARCHAR
        );
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS bronze.user_sessions (
            session_id VARCHAR,
            user_id VARCHAR,
            session_timestamp VARCHAR
        );
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS bronze.loans (
            loan_id VARCHAR,
            user_id VARCHAR,
            disbursement_date VARCHAR,
            amount VARCHAR,
            term_months VARCHAR,
            updated_at VARCHAR,
            ingestion_timestamp VARCHAR
        );
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS bronze.loan_payments (
            payment_id VARCHAR,
            loan_id VARCHAR,
            due_date VARCHAR,
            payment_date VARCHAR,
            amount_due VARCHAR,
            amount_paid VARCHAR,
            updated_at VARCHAR,
            ingestion_timestamp VARCHAR
        );
        """)
        
        # Silver Tables (Cleaned, Deduplicated, Typed)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS silver.users (
            user_id VARCHAR PRIMARY KEY,
            created_at TIMESTAMP,
            country VARCHAR,
            updated_at TIMESTAMP,
            ingestion_timestamp TIMESTAMP
        );
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS silver.user_sessions (
            session_id VARCHAR PRIMARY KEY,
            user_id VARCHAR,
            session_timestamp TIMESTAMP
        );
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS silver.loans (
            loan_id VARCHAR PRIMARY KEY,
            user_id VARCHAR,
            disbursement_date DATE,
            amount DOUBLE,
            term_months INTEGER,
            updated_at TIMESTAMP,
            ingestion_timestamp TIMESTAMP
        );
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS silver.loan_payments (
            payment_id VARCHAR PRIMARY KEY,
            loan_id VARCHAR,
            due_date DATE,
            payment_date DATE,
            amount_due DOUBLE,
            amount_paid DOUBLE,
            updated_at TIMESTAMP,
            ingestion_timestamp TIMESTAMP
        );
        """)
        
        # Gold Table (Aggregated variables and target indicators)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS gold.target_construction (
            user_id VARCHAR NOT NULL,
            observation_date DATE NOT NULL,
            monthly_volume DOUBLE NOT NULL,
            session_regularity INTEGER NOT NULL,
            target_default_30d INTEGER NOT NULL,
            PRIMARY KEY (user_id, observation_date)
        );
        """)
        logger.info("Database schemas initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing schemas: {e}")
        raise e
    finally:
        conn.close()

def insert_dicts_to_bronze(conn: duckdb.DuckDBPyConnection, table_name: str, records: List[Dict[str, Any]]) -> int:
    """Inserts a list of dictionaries into a Bronze table with string values."""
    if not records:
        return 0
    
    # Get columns of target table
    desc = conn.execute(f"DESCRIBE bronze.{table_name}").fetchall()
    columns = [col[0] for col in desc]
    
    placeholders = ", ".join(["?" for _ in columns])
    query = f"INSERT INTO bronze.{table_name} ({', '.join(columns)}) VALUES ({placeholders})"
    
    rows_to_insert = []
    for r in records:
        row = []
        for col in columns:
            val = r.get(col, None)
            row.append(str(val) if val is not None else None)
        rows_to_insert.append(row)
        
    conn.executemany(query, rows_to_insert)
    return len(records)

@task(retries=3, retry_delay_seconds=10)
def ingest_to_bronze_task(db_path: str, raw_data_dir_or_dicts: Union[str, Dict[str, List[Dict[str, Any]]]]) -> Dict[str, int]:
    """Prefect task to ingest raw transaction and customer records into Bronze tables."""
    logger.info("Executing ingest_to_bronze_task...")
    conn = duckdb.connect(db_path)
    counts = {}
    try:
        if isinstance(raw_data_dir_or_dicts, dict):
            # Ingest dictionaries directly
            for table_name in ["users", "user_sessions", "loans", "loan_payments"]:
                records = raw_data_dir_or_dicts.get(table_name, [])
                inserted = insert_dicts_to_bronze(conn, table_name, records)
                counts[table_name] = inserted
                logger.info(f"Ingested {inserted} records into bronze.{table_name}")
        elif isinstance(raw_data_dir_or_dicts, str) and os.path.isdir(raw_data_dir_or_dicts):
            # Ingest from CSV/JSON in directory
            for table_name in ["users", "user_sessions", "loans", "loan_payments"]:
                csv_path = os.path.join(raw_data_dir_or_dicts, f"{table_name}.csv")
                json_path = os.path.join(raw_data_dir_or_dicts, f"{table_name}.json")
                if os.path.exists(json_path):
                    with open(json_path, "r", encoding="utf-8") as f:
                        records = json.load(f)
                    inserted = insert_dicts_to_bronze(conn, table_name, records)
                    counts[table_name] = inserted
                    logger.info(f"Ingested {inserted} records from JSON file into bronze.{table_name}")
                elif os.path.exists(csv_path):
                    # Use DuckDB's CSV reader to insert append-only
                    path_str = csv_path.replace(os.sep, "/")
                    query = f"INSERT INTO bronze.{table_name} SELECT * FROM read_csv_auto('{path_str}', all_varchar=True)"
                    conn.execute(query)
                    inserted = conn.execute(f"SELECT COUNT(*) FROM bronze.{table_name}").fetchone()[0]
                    counts[table_name] = inserted
                    logger.info(f"Ingested CSV file into bronze.{table_name}")
                else:
                    counts[table_name] = 0
                    logger.warning(f"No source files found for table: {table_name}")
        else:
            raise ValueError("raw_data_dir_or_dicts must be a dictionary of records or a path to a directory containing raw CSVs/JSONs.")
        return counts
    except Exception as e:
        logger.error(f"Failed ingest_to_bronze_task: {e}")
        raise e
    finally:
        conn.close()

@task(retries=3, retry_delay_seconds=10)
def transform_to_silver_task(db_path: str) -> Dict[str, int]:
    """Prefect task to clean, parse, and deduplicate Bronze records into Silver tables inside a transaction."""
    logger.info("Executing transform_to_silver_task...")
    conn = duckdb.connect(db_path)
    counts = {}
    try:
        conn.execute("BEGIN TRANSACTION;")
        
        # 1. users deduplication & cleaning
        conn.execute("""
        INSERT OR REPLACE INTO silver.users
        SELECT user_id, created_at, country, updated_at, ingestion_timestamp
        FROM (
          SELECT
            user_id,
            COALESCE(TRY_CAST(replace(created_at, '/', '-') AS TIMESTAMP), try_strptime(created_at, '%d-%m-%Y %H:%M:%S')) AS created_at,
            country,
            COALESCE(TRY_CAST(replace(updated_at, '/', '-') AS TIMESTAMP), try_strptime(updated_at, '%d-%m-%Y %H:%M:%S')) AS updated_at,
            COALESCE(TRY_CAST(replace(ingestion_timestamp, '/', '-') AS TIMESTAMP), try_strptime(ingestion_timestamp, '%d-%m-%Y %H:%M:%S')) AS ingestion_timestamp,
            ROW_NUMBER() OVER (
              PARTITION BY user_id
              ORDER BY 
                COALESCE(TRY_CAST(replace(updated_at, '/', '-') AS TIMESTAMP), try_strptime(updated_at, '%d-%m-%Y %H:%M:%S')) DESC,
                COALESCE(TRY_CAST(replace(ingestion_timestamp, '/', '-') AS TIMESTAMP), try_strptime(ingestion_timestamp, '%d-%m-%Y %H:%M:%S')) DESC
            ) as row_num
          FROM bronze.users
          WHERE user_id IS NOT NULL
        )
        WHERE row_num = 1;
        """)
        
        # 2. user_sessions deduplication & cleaning
        conn.execute("""
        INSERT OR REPLACE INTO silver.user_sessions
        SELECT session_id, user_id, session_timestamp
        FROM (
          SELECT
            session_id,
            user_id,
            COALESCE(TRY_CAST(replace(session_timestamp, '/', '-') AS TIMESTAMP), try_strptime(session_timestamp, '%d-%m-%Y %H:%M:%S')) AS session_timestamp,
            ROW_NUMBER() OVER (
              PARTITION BY session_id
              ORDER BY 
                COALESCE(TRY_CAST(replace(session_timestamp, '/', '-') AS TIMESTAMP), try_strptime(session_timestamp, '%d-%m-%Y %H:%M:%S')) DESC
            ) as row_num
          FROM bronze.user_sessions
          WHERE session_id IS NOT NULL AND user_id IS NOT NULL
        )
        WHERE row_num = 1;
        """)
        
        # 3. loans deduplication & cleaning
        conn.execute("""
        INSERT OR REPLACE INTO silver.loans
        SELECT loan_id, user_id, disbursement_date, amount, term_months, updated_at, ingestion_timestamp
        FROM (
          SELECT
            loan_id,
            user_id,
            COALESCE(TRY_CAST(replace(disbursement_date, '/', '-') AS DATE), CAST(try_strptime(disbursement_date, '%d-%m-%Y') AS DATE)) AS disbursement_date,
            TRY_CAST(amount AS DOUBLE) AS amount,
            TRY_CAST(term_months AS INTEGER) AS term_months,
            COALESCE(TRY_CAST(replace(updated_at, '/', '-') AS TIMESTAMP), try_strptime(updated_at, '%d-%m-%Y %H:%M:%S')) AS updated_at,
            COALESCE(TRY_CAST(replace(ingestion_timestamp, '/', '-') AS TIMESTAMP), try_strptime(ingestion_timestamp, '%d-%m-%Y %H:%M:%S')) AS ingestion_timestamp,
            ROW_NUMBER() OVER (
              PARTITION BY loan_id
              ORDER BY 
                COALESCE(TRY_CAST(replace(updated_at, '/', '-') AS TIMESTAMP), try_strptime(updated_at, '%d-%m-%Y %H:%M:%S')) DESC,
                COALESCE(TRY_CAST(replace(ingestion_timestamp, '/', '-') AS TIMESTAMP), try_strptime(ingestion_timestamp, '%d-%m-%Y %H:%M:%S')) DESC
            ) as row_num
          FROM bronze.loans
          WHERE loan_id IS NOT NULL AND user_id IS NOT NULL
        )
        WHERE row_num = 1
          AND disbursement_date IS NOT NULL
          AND amount IS NOT NULL;
        """)
        
        # 4. loan_payments deduplication & cleaning
        conn.execute("""
        INSERT OR REPLACE INTO silver.loan_payments
        SELECT payment_id, loan_id, due_date, payment_date, amount_due, amount_paid, updated_at, ingestion_timestamp
        FROM (
          SELECT
            payment_id,
            loan_id,
            COALESCE(TRY_CAST(replace(due_date, '/', '-') AS DATE), CAST(try_strptime(due_date, '%d-%m-%Y') AS DATE)) AS due_date,
            COALESCE(TRY_CAST(replace(payment_date, '/', '-') AS DATE), CAST(try_strptime(payment_date, '%d-%m-%Y') AS DATE)) AS payment_date,
            TRY_CAST(amount_due AS DOUBLE) AS amount_due,
            TRY_CAST(amount_paid AS DOUBLE) AS amount_paid,
            COALESCE(TRY_CAST(replace(updated_at, '/', '-') AS TIMESTAMP), try_strptime(updated_at, '%d-%m-%Y %H:%M:%S')) AS updated_at,
            COALESCE(TRY_CAST(replace(ingestion_timestamp, '/', '-') AS TIMESTAMP), try_strptime(ingestion_timestamp, '%d-%m-%Y %H:%M:%S')) AS ingestion_timestamp,
            ROW_NUMBER() OVER (
              PARTITION BY payment_id
              ORDER BY 
                COALESCE(TRY_CAST(replace(updated_at, '/', '-') AS TIMESTAMP), try_strptime(updated_at, '%d-%m-%Y %H:%M:%S')) DESC,
                COALESCE(TRY_CAST(replace(ingestion_timestamp, '/', '-') AS TIMESTAMP), try_strptime(ingestion_timestamp, '%d-%m-%Y %H:%M:%S')) DESC
            ) as row_num
          FROM bronze.loan_payments
          WHERE payment_id IS NOT NULL AND loan_id IS NOT NULL
        )
        WHERE row_num = 1
          AND due_date IS NOT NULL;
        """)
        
        conn.execute("COMMIT;")
        
        # Retrieve row counts for response
        counts["users"] = conn.execute("SELECT COUNT(*) FROM silver.users").fetchone()[0]
        counts["user_sessions"] = conn.execute("SELECT COUNT(*) FROM silver.user_sessions").fetchone()[0]
        counts["loans"] = conn.execute("SELECT COUNT(*) FROM silver.loans").fetchone()[0]
        counts["loan_payments"] = conn.execute("SELECT COUNT(*) FROM silver.loan_payments").fetchone()[0]
        
        logger.info(f"Silver tables successfully updated. Row counts: {counts}")
        return counts
    except Exception as e:
        logger.error(f"Error in transform_to_silver_task: {e}")
        try:
            conn.execute("ROLLBACK;")
        except Exception:
            pass
        raise e
    finally:
        conn.close()

def run_quality_audit(conn: duckdb.DuckDBPyConnection) -> Dict[str, int]:
    """Executes the data quality audit and returns anomaly counts."""
    logger.info("Executing quality audit on Bronze tables...")
    audit_sql = load_sql_query("audit_data")
    
    res = conn.execute(audit_sql).fetchone()
    desc = conn.execute(audit_sql).description
    columns = [col[0] for col in desc]
    anomalies = dict(zip(columns, res))
    
    for k, v in anomalies.items():
        if v > 0:
            logger.warning(f"Data Quality Anomaly: {k} = {v} invalid/duplicate records detected.")
            
    return anomalies

@task(retries=3, retry_delay_seconds=10)
def build_gold_features_task(db_path: str, observation_date: str) -> Dict[str, int]:
    """Prefect task to calculate behavioral metrics and default target per user and cohort merge into Gold."""
    logger.info(f"Executing build_gold_features_task for date: {observation_date}")
    conn = duckdb.connect(db_path)
    try:
        # 1. Run audit
        run_quality_audit(conn)
        
        # 2. Extract features
        extract_sql = load_sql_query("extract_features")
        features_res = conn.execute(extract_sql, [observation_date] * 5).fetchall()
        f_desc = conn.execute(extract_sql, [observation_date] * 5).description
        f_columns = [col[0] for col in f_desc]
        features = [dict(zip(f_columns, row)) for row in features_res]
        
        # 3. Build target
        target_sql = load_sql_query("build_target")
        target_res = conn.execute(target_sql, [observation_date] * 3).fetchall()
        t_desc = conn.execute(target_sql, [observation_date] * 3).description
        t_columns = [col[0] for col in t_desc]
        targets = [dict(zip(t_columns, row)) for row in target_res]
        
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
                
        # 5. Create temp staging table
        conn.execute("DROP TABLE IF EXISTS staged_target_construction;")
        conn.execute("""
        CREATE TEMP TABLE staged_target_construction (
            user_id VARCHAR,
            observation_date DATE,
            monthly_volume DOUBLE,
            session_regularity INTEGER,
            target_default_30d INTEGER
        );
        """)
        
        rows_to_insert = [
            (
                r["user_id"],
                r["observation_date"],
                r["monthly_volume"],
                r["session_regularity"],
                r["target_default_30d"]
            )
            for r in combined.values()
        ]
        
        if rows_to_insert:
            conn.executemany("INSERT INTO staged_target_construction VALUES (?, ?, ?, ?, ?)", rows_to_insert)
            
            # 6. Idempotent Merge into gold
            merge_sql = load_sql_query("merge_target_construction")
            conn.execute(merge_sql)
            
        inserted_count = len(rows_to_insert)
        logger.info(f"Gold table target_construction updated with {inserted_count} records.")
        return {"inserted_count": inserted_count}
    except Exception as e:
        logger.error(f"Error in build_gold_features_task: {e}")
        raise e
    finally:
        conn.close()

@task(retries=3, retry_delay_seconds=10)
def run_alerts_task(db_path: str, observation_date: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Prefect task to evaluate cohort default rates and log a quality warning alert if > 15%."""
    logger.info("Executing run_alerts_task...")
    conn = duckdb.connect(db_path)
    try:
        query = """
        SELECT 
          strftime(u.created_at, '%Y-%m') AS reg_month,
          AVG(CAST(c.target_default_30d AS DOUBLE)) AS default_rate,
          COUNT(*) AS cohort_size
        FROM gold.target_construction c
        JOIN silver.users u ON c.user_id = u.user_id
        WHERE c.observation_date = CAST(? AS DATE)
        GROUP BY reg_month;
        """
        res = conn.execute(query, [observation_date]).fetchall()
        desc = conn.execute(query, [observation_date]).description
        columns = [col[0] for col in desc]
        results = [dict(zip(columns, row)) for row in res]
        
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
                    f"**Default Rate**: {alert['default_rate'] * 100:.2f}% | "
                    f"**Cohort Size**: {alert['cohort_size']} users\n"
                )
        return results, drift_report
    except Exception as e:
        logger.error(f"Error in run_alerts_task: {e}")
        raise e
    finally:
        conn.close()

@flow(name="medallion_pipeline_flow")
def medallion_pipeline_flow(observation_date: str, db_path: str, raw_data_dir_or_dicts: Union[str, Dict[str, List[Dict[str, Any]]]]) -> Dict[str, Any]:
    """Prefect flow orchestrating the Medallion DuckDB Data Pipeline."""
    logger.info(f"Starting Medallion Prefect flow for date: {observation_date} on db: {db_path}")
    
    # 1. Ingest Bronze
    ingest_res = ingest_to_bronze_task(db_path, raw_data_dir_or_dicts)
    
    # 2. Transform Silver (sequential execution enforced)
    silver_res = transform_to_silver_task(db_path, wait_for=[ingest_res])
    
    # 3. Build Gold Features (sequential execution enforced)
    gold_res = build_gold_features_task(db_path, observation_date, wait_for=[silver_res])
    
    # 4. Run Cohort Alerts (sequential execution enforced)
    alerts_res = run_alerts_task(db_path, observation_date, wait_for=[gold_res])
    
    return {
        "ingest_summary": ingest_res,
        "silver_summary": silver_res,
        "gold_summary": gold_res,
        "alerts_summary": alerts_res[0],
        "drift_report": alerts_res[1]
    }
