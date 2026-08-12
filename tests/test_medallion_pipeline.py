import os
import tempfile
import unittest
import duckdb
from prefect.testing.utilities import prefect_test_harness
from src.data.medallion_pipeline import (
    initialize_duckdb_schemas,
    ingest_to_bronze_task,
    transform_to_silver_task,
    build_gold_features_task,
    run_alerts_task,
    medallion_pipeline_flow
)

class TestMedallionPipeline(unittest.TestCase):
    def setUp(self) -> None:
        """Create a temporary file-based DuckDB database and initialize schemas."""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.db_fd)  # Close immediately to release the file lock on Windows
        if os.path.exists(self.db_path):
            os.remove(self.db_path)  # Remove the 0-byte empty file so DuckDB can initialize it from scratch
        initialize_duckdb_schemas(self.db_path)
        self.mock_data = self.get_mock_data()

    def tearDown(self) -> None:
        """Close resources and clean up the database file."""
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def get_mock_data(self) -> dict:
        """Generates test raw data matching target scenarios and edge cases."""
        users = [
            # normal user
            {"user_id": "user_1", "created_at": "2024-05-15 10:00:00", "country": "MX", "updated_at": "2024-05-15 10:00:00", "ingestion_timestamp": "2024-05-15 10:00:00"},
            # duplicate user_id with newer updated_at (should be chosen)
            {"user_id": "user_1", "created_at": "2024-05-15 10:00:00", "country": "MX", "updated_at": "2024-05-16 11:00:00", "ingestion_timestamp": "2024-05-16 11:00:00"},
            {"user_id": "user_2", "created_at": "2024-06-10 12:00:00", "country": "BR", "updated_at": "2024-06-10 12:00:00", "ingestion_timestamp": "2024-06-10 12:00:00"},
            {"user_id": "user_3", "created_at": "2024-06-20 14:00:00", "country": "AR", "updated_at": "2024-06-20 14:00:00", "ingestion_timestamp": "2024-06-20 14:00:00"},
            # user with NULL user_id (should be filtered out)
            {"user_id": None, "created_at": "2024-07-01 00:00:00", "country": "BR", "updated_at": "2024-07-01 00:00:00", "ingestion_timestamp": "2024-07-01 00:00:00"},
        ]

        # 30-day window for observation_date '2025-01-01' is 2024-12-02 to 2025-01-01
        sessions = [
            # user_1: 2 distinct days in window, 1 session outside window
            {"session_id": "sess_1", "user_id": "user_1", "session_timestamp": "2024-12-05 10:00:00"},
            {"session_id": "sess_2", "user_id": "user_1", "session_timestamp": "2024-12-05 14:00:00"},  # Same day as sess_1
            {"session_id": "sess_3", "user_id": "user_1", "session_timestamp": "2024-12-10 09:00:00"},  # Different day
            {"session_id": "sess_4", "user_id": "user_1", "session_timestamp": "2024-11-20 12:00:00"},  # Outside 30 days
            
            # user_2: 1 distinct day in window
            {"session_id": "sess_5", "user_id": "user_2", "session_timestamp": "2024-12-15 00:00:00"},
            
            # null session_id (should be filtered out)
            {"session_id": None, "user_id": "user_2", "session_timestamp": "2024-12-15 00:00:00"},
            # null user_id (should be filtered out)
            {"session_id": "sess_6", "user_id": None, "session_timestamp": "2024-12-15 00:00:00"},
        ]

        # 30-day window is 2024-12-02 to 2025-01-01
        loans = [
            # user_1: loan_1 (in window), loan_2 (outside window)
            {"loan_id": "loan_1", "user_id": "user_1", "disbursement_date": "2024-12-10", "amount": "1000.0", "term_months": "12", "updated_at": "2024-12-10 10:00:00", "ingestion_timestamp": "2024-12-10 10:00:00"},
            {"loan_id": "loan_2", "user_id": "user_1", "disbursement_date": "2024-11-15", "amount": "500.0", "term_months": "6", "updated_at": "2024-11-15 10:00:00", "ingestion_timestamp": "2024-11-15 10:00:00"},
            
            # user_2: loan_3 (in window, non-standard date format, duplicate PK)
            {"loan_id": "loan_3", "user_id": "user_2", "disbursement_date": "2024/12/20", "amount": "2000.0", "term_months": "12", "updated_at": "2024-12-20 12:00:00", "ingestion_timestamp": "2024-12-20 12:00:00"},
            {"loan_id": "loan_3", "user_id": "user_2", "disbursement_date": "2024/12/20", "amount": "2500.0", "term_months": "12", "updated_at": "2024-12-21 12:00:00", "ingestion_timestamp": "2024-12-21 12:00:00"}, # Duplicate loan_3 (should overwrite to 2500)
            
            # null PK / null user
            {"loan_id": None, "user_id": "user_2", "disbursement_date": "2024-12-20", "amount": "1000.0", "term_months": "12", "updated_at": "2024-12-20 12:00:00", "ingestion_timestamp": "2024-12-20 12:00:00"},
            {"loan_id": "loan_4", "user_id": None, "disbursement_date": "2024-12-20", "amount": "1000.0", "term_months": "12", "updated_at": "2024-12-20 12:00:00", "ingestion_timestamp": "2024-12-20 12:00:00"},
            
            # malformed fields (should be filtered out or handled)
            {"loan_id": "loan_5", "user_id": "user_2", "disbursement_date": "invalid-date", "amount": "1000.0", "term_months": "12", "updated_at": "2024-12-20 12:00:00", "ingestion_timestamp": "2024-12-20 12:00:00"},
            {"loan_id": "loan_6", "user_id": "user_2", "disbursement_date": "2024-12-20", "amount": "invalid-amount", "term_months": "12", "updated_at": "2024-12-20 12:00:00", "ingestion_timestamp": "2024-12-20 12:00:00"},
        ]

        # 12-month performance window is 2025-01-02 to 2026-01-01
        payments = [
            # For loan_1 (user_1): paid 46 days late (DPD = 46) -> target_default_30d = 1
            {"payment_id": "pay_1", "loan_id": "loan_1", "due_date": "2025-02-10", "payment_date": "2025-02-15", "amount_due": "100.0", "amount_paid": "100.0", "updated_at": "2025-02-15 10:00:00", "ingestion_timestamp": "2025-02-15 10:00:00"},
            {"payment_id": "pay_2", "loan_id": "loan_1", "due_date": "2025-03-10", "payment_date": "2025-04-25", "amount_due": "100.0", "amount_paid": "100.0", "updated_at": "2025-04-25 10:00:00", "ingestion_timestamp": "2025-04-25 10:00:00"}, # DPD = 46
            
            # For loan_3 (user_2): paid 5 days late (DPD = 5) -> target_default_30d = 0
            {"payment_id": "pay_3", "loan_id": "loan_3", "due_date": "2025-01-20", "payment_date": "2025-01-25", "amount_due": "200.0", "amount_paid": "200.0", "updated_at": "2025-01-25 12:00:00", "ingestion_timestamp": "2025-01-25 12:00:00"},
            {"payment_id": "pay_4", "loan_id": "loan_3", "due_date": "2025-02-20", "payment_date": "2025-02-22", "amount_due": "200.0", "amount_paid": "200.0", "updated_at": "2025-02-22 12:00:00", "ingestion_timestamp": "2025-02-22 12:00:00"},
            
            # Payment outside 12-month window (should be ignored)
            {"payment_id": "pay_5", "loan_id": "loan_1", "due_date": "2026-02-10", "payment_date": "2026-03-25", "amount_due": "100.0", "amount_paid": "100.0", "updated_at": "2026-03-25 10:00:00", "ingestion_timestamp": "2026-03-25 10:00:00"},
            
            # Duplicate payment PK
            {"payment_id": "pay_3", "loan_id": "loan_3", "due_date": "2025-01-20", "payment_date": "2025-01-25", "amount_due": "200.0", "amount_paid": "200.0", "updated_at": "2025-01-26 12:00:00", "ingestion_timestamp": "2025-01-26 12:00:00"},
        ]

        return {
            "users": users,
            "user_sessions": sessions,
            "loans": loans,
            "loan_payments": payments
        }

    def test_bronze_raw_load(self) -> None:
        """Requirement A4: Verify raw ingestion preserves duplicates and nulls in Bronze."""
        ingest_to_bronze_task.fn(self.db_path, self.mock_data)
        
        conn = duckdb.connect(self.db_path)
        try:
            # Check users raw count including duplicate and null user
            users_count = conn.execute("SELECT COUNT(*) FROM bronze.users").fetchone()[0]
            self.assertEqual(users_count, 5)
            
            # Check sessions raw count including duplicate/null
            sessions_count = conn.execute("SELECT COUNT(*) FROM bronze.user_sessions").fetchone()[0]
            self.assertEqual(sessions_count, 7)
            
            # Check loans raw count
            loans_count = conn.execute("SELECT COUNT(*) FROM bronze.loans").fetchone()[0]
            self.assertEqual(loans_count, 8)
            
            # Check payments raw count
            payments_count = conn.execute("SELECT COUNT(*) FROM bronze.loan_payments").fetchone()[0]
            self.assertEqual(payments_count, 6)
        finally:
            conn.close()

    def test_silver_deduplication_and_normalization(self) -> None:
        """Requirements A5 & A6: Verify Silver layer deduplication, primary/foreign key filtering, and format normalization."""
        # 1. Ingest to Bronze
        ingest_to_bronze_task.fn(self.db_path, self.mock_data)
        
        # 2. Run Silver Transformation
        transform_to_silver_task.fn(self.db_path)
        
        conn = duckdb.connect(self.db_path)
        try:
            # A5: user_1 duplicate resolved, null PK filtered out
            users = conn.execute("SELECT user_id, updated_at FROM silver.users ORDER BY user_id").fetchall()
            self.assertEqual(len(users), 3)  # user_1, user_2, user_3 (null user_id excluded)
            self.assertEqual(users[0][0], "user_1")
            # Should have chosen the one with updated_at = 2024-05-16
            self.assertEqual(str(users[0][1]), "2024-05-16 11:00:00")
            
            # A5: sessions filtered
            sessions = conn.execute("SELECT session_id FROM silver.user_sessions").fetchall()
            self.assertEqual(len(sessions), 5)  # sess_1, sess_2, sess_3, sess_4, sess_5 (null/invalid sessions excluded)
            
            # A5 & A6: loans deduplicated, normalized, malformed rows filtered
            loans = conn.execute("SELECT loan_id, amount, disbursement_date FROM silver.loans ORDER BY loan_id").fetchall()
            self.assertEqual(len(loans), 3)  # loan_1, loan_2, loan_3 (duplicate resolved, malformed dates/amounts and null PKs excluded)
            # loan_3 amount should be deduplicated to the latest (2500.0)
            self.assertEqual(loans[2][0], "loan_3")
            self.assertEqual(loans[2][1], 2500.0)
            # Date normalized to Date type
            self.assertEqual(str(loans[2][2]), "2024-12-20")
            
            # A5: payments deduplicated and validated
            payments = conn.execute("SELECT payment_id FROM silver.loan_payments").fetchall()
            self.assertEqual(len(payments), 5)  # pay_1, pay_2, pay_3, pay_4, pay_5 (pay_5 included in silver, pay_3 duplicate resolved)
        finally:
            conn.close()

    def test_monthly_volume(self) -> None:
        """Requirement A1: Verify user monthly loan volume calculation in Gold."""
        ingest_to_bronze_task.fn(self.db_path, self.mock_data)
        transform_to_silver_task.fn(self.db_path)
        build_gold_features_task.fn(self.db_path, "2025-01-01")
        
        conn = duckdb.connect(self.db_path)
        try:
            # Check user volumes
            # user_1: loan_1 (1000.0, in window), loan_2 (500.0, outside window) -> monthly_volume = 1000.0
            u1_vol = conn.execute("SELECT monthly_volume FROM gold.target_construction WHERE user_id = 'user_1'").fetchone()[0]
            self.assertEqual(u1_vol, 1000.0)
            
            # user_2: loan_3 (2500.0, in window) -> monthly_volume = 2500.0
            u2_vol = conn.execute("SELECT monthly_volume FROM gold.target_construction WHERE user_id = 'user_2'").fetchone()[0]
            self.assertEqual(u2_vol, 2500.0)
            
            # user_3: no loans -> monthly_volume = 0.0
            u3_vol = conn.execute("SELECT monthly_volume FROM gold.target_construction WHERE user_id = 'user_3'").fetchone()[0]
            self.assertEqual(u3_vol, 0.0)
        finally:
            conn.close()

    def test_session_regularity(self) -> None:
        """Requirement A2: Verify user session regularity calculation in Gold."""
        ingest_to_bronze_task.fn(self.db_path, self.mock_data)
        transform_to_silver_task.fn(self.db_path)
        build_gold_features_task.fn(self.db_path, "2025-01-01")
        
        conn = duckdb.connect(self.db_path)
        try:
            # user_1: 3 sessions. sess_1 & sess_2 on 2024-12-05 (1 day), sess_3 on 2024-12-10 (1 day), sess_4 outside (0 day) -> session_regularity = 2
            u1_reg = conn.execute("SELECT session_regularity FROM gold.target_construction WHERE user_id = 'user_1'").fetchone()[0]
            self.assertEqual(u1_reg, 2)
            
            # user_2: sess_5 on 2024-12-15 -> session_regularity = 1
            u2_reg = conn.execute("SELECT session_regularity FROM gold.target_construction WHERE user_id = 'user_2'").fetchone()[0]
            self.assertEqual(u2_reg, 1)
            
            # user_3: no sessions -> session_regularity = 0
            u3_reg = conn.execute("SELECT session_regularity FROM gold.target_construction WHERE user_id = 'user_3'").fetchone()[0]
            self.assertEqual(u3_reg, 0)
        finally:
            conn.close()

    def test_target_default_indicator(self) -> None:
        """Requirement A3: Verify target default variable default status inside the 12-month window."""
        ingest_to_bronze_task.fn(self.db_path, self.mock_data)
        transform_to_silver_task.fn(self.db_path)
        build_gold_features_task.fn(self.db_path, "2025-01-01")
        
        conn = duckdb.connect(self.db_path)
        try:
            # user_1: pay_2 is 46 days late (exceeds 30 DPD), due within 12 months -> target_default_30d = 1
            u1_def = conn.execute("SELECT target_default_30d FROM gold.target_construction WHERE user_id = 'user_1'").fetchone()[0]
            self.assertEqual(u1_def, 1)
            
            # user_2: pay_3 and pay_4 are <= 30 DPD -> target_default_30d = 0
            u2_def = conn.execute("SELECT target_default_30d FROM gold.target_construction WHERE user_id = 'user_2'").fetchone()[0]
            self.assertEqual(u2_def, 0)
            
            # user_3: no payments -> target_default_30d = 0
            u3_def = conn.execute("SELECT target_default_30d FROM gold.target_construction WHERE user_id = 'user_3'").fetchone()[0]
            self.assertEqual(u3_def, 0)
        finally:
            conn.close()

    def test_cohort_default_alert(self) -> None:
        """Requirement A7: Verify alerting behavior and warnings when monthly default rate exceeds 15%."""
        ingest_to_bronze_task.fn(self.db_path, self.mock_data)
        transform_to_silver_task.fn(self.db_path)
        build_gold_features_task.fn(self.db_path, "2025-01-01")
        
        results, drift_report = run_alerts_task.fn(self.db_path, "2025-01-01")
        
        # Cohort registrations:
        # registration month 2024-05 (user_1): default = 1 -> rate = 100% (exceeds 15% alert)
        # registration month 2024-06 (user_2, user_3): defaults = 0, 0 -> rate = 0%
        
        self.assertIsNotNone(drift_report)
        self.assertIn("2024-05", drift_report)
        self.assertIn("100.00%", drift_report)
        self.assertNotIn("2024-06", drift_report)

    def test_prefect_flow_orchestration(self) -> None:
        """Requirement A8: Verify Prefect flow coordinates all tasks sequentially and successfully."""
        with prefect_test_harness():
            res = medallion_pipeline_flow(
                observation_date="2025-01-01",
                db_path=self.db_path,
                raw_data_dir_or_dicts=self.mock_data
            )
            
            self.assertIn("ingest_summary", res)
            self.assertIn("silver_summary", res)
            self.assertIn("gold_summary", res)
            self.assertIn("alerts_summary", res)
            self.assertIn("drift_report", res)
            
            self.assertEqual(res["ingest_summary"]["users"], 5)
            self.assertEqual(res["silver_summary"]["users"], 3)
            self.assertEqual(res["gold_summary"]["inserted_count"], 3)
            self.assertIsNotNone(res["drift_report"])

if __name__ == "__main__":
    unittest.main()
