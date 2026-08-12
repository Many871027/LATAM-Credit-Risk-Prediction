import os
import argparse
import logging
from src.data.medallion_pipeline import initialize_duckdb_schemas, medallion_pipeline_flow

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RunPipeline")

def main() -> None:
    """Main entry point to execute the Medallion database pipeline."""
    parser = argparse.ArgumentParser(description="Run the Medallion DuckDB Prefect Pipeline.")
    parser.add_argument(
        "--observation-date",
        type=str,
        default="2025-01-01",
        help="Observation cohort snapshot date (YYYY-MM-DD)."
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="credit_risk_medallion.db",
        help="Path to the DuckDB database file."
    )
    parser.add_argument(
        "--raw-data-dir",
        type=str,
        default="data/raw",
        help="Directory containing the raw CSV/JSON files."
    )
    
    args = parser.parse_args()
    
    logger.info("Starting pipeline run script...")
    logger.info(f"DB Path: {args.db_path}")
    logger.info(f"Observation Date: {args.observation_date}")
    logger.info(f"Raw Data Directory: {args.raw_data_dir}")
    
    # 1. Initialize schemas and tables
    initialize_duckdb_schemas(args.db_path)
    
    # 2. Check if raw data directory exists
    if not os.path.exists(args.raw_data_dir):
        logger.warning(
            f"Raw data directory '{args.raw_data_dir}' not found. "
            "Proceeding with Prefect flow execution (tasks may skip or ingest empty datasets if no records provided)."
        )
    
    # 3. Execute the Prefect flow
    logger.info("Executing Medallion Pipeline Flow...")
    results = medallion_pipeline_flow(
        observation_date=args.observation_date,
        db_path=args.db_path,
        raw_data_dir_or_dicts=args.raw_data_dir
    )
    
    logger.info("Pipeline Flow completed.")
    
    # 4. Print Summary Results
    print("\n" + "=" * 50)
    print("           MEDALLION PIPELINE RUN SUMMARY")
    print("=" * 50)
    print(f"Bronze Ingested Row Counts:")
    for k, v in results["ingest_summary"].items():
        print(f"  - {k}: {v}")
    print("-" * 50)
    print(f"Silver Cleaned & Deduplicated Row Counts:")
    for k, v in results["silver_summary"].items():
        print(f"  - {k}: {v}")
    print("-" * 50)
    print(f"Gold Aggregated target construction rows: {results['gold_summary']['inserted_count']}")
    
    if results["drift_report"]:
        print("\n" + "=" * 50)
        print("                 DIAGNOSTIC DRIFT REPORT")
        print("=" * 50)
        print(results["drift_report"])
        print("=" * 50)
    else:
        print("\nAll cohorts are performing within the acceptable default rate (< 15%).")
        print("=" * 50)

if __name__ == "__main__":
    main()
