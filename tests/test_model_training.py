import unittest
import os
import numpy as np
import pandas as pd
import duckdb
import joblib
import skops.io as sio
from sklearn.datasets import make_classification
import xgboost as xgb

from src.models.metrics import (
    calculate_roc_auc,
    calculate_gini,
    calculate_ks
)
from src.models.train import (
    load_training_data,
    split_and_impute_data,
    train_pipeline,
    ModelValidationException
)
from src.models.registry import save_model

class TestModelTrainingPipeline(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = "test_risk_model.db"
        # Setup fresh DuckDB test DB
        conn = duckdb.connect(self.db_path)
        conn.execute("CREATE SCHEMA IF NOT EXISTS gold;")
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
        
        # Populate with 40 records (30 non-default, 10 default) to ensure stratified split is feasible
        records = []
        for i in range(40):
            target = 1 if i < 10 else 0
            records.append((
                f"user_{i}",
                "2025-01-01",
                float(2000 * (i + 1)),
                (i % 30) + 1,
                target
            ))
            
        conn.executemany(
            "INSERT INTO gold.target_construction VALUES (?, ?, ?, ?, ?)",
            records
        )
        conn.close()
        self.output_base = "test_output_model"

    def tearDown(self) -> None:
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        for ext in [".joblib", ".skops"]:
            path = f"{self.output_base}{ext}"
            if os.path.exists(path):
                os.remove(path)

    def test_load_training_data(self) -> None:
        # A3: Test loading training data
        df = load_training_data(self.db_path, "2025-01-01")
        self.assertFalse(df.empty)
        self.assertEqual(len(df), 40)
        
        # Verify columns exist
        expected_cols = {"user_id", "monthly_volume", "session_regularity", "target_default_30d", "income"}
        self.assertTrue(expected_cols.issubset(df.columns))
        
        # Verify synthetic income values are non-negative and >= 15000
        self.assertTrue((df["income"] >= 15000.0).all())

    def test_split_and_impute_data(self) -> None:
        # A3 & A7: Test stratified splitting and imputation rules
        # Create a dataframe with some anomalies
        raw_data = {
            "user_id": [f"user_{i}" for i in range(20)],
            "monthly_volume": [-100.0] + [2000.0] * 19,  # Negative volume
            "session_regularity": [40] + [15] * 19,       # regularity > 30
            "income": [None, -5000.0, np.inf] + [25000.0] * 17, # Null, negative, infinity
            "target_default_30d": [1] * 5 + [0] * 15      # target for stratification
        }
        df = pd.DataFrame(raw_data)
        
        feature_cols = ["monthly_volume", "session_regularity", "income"]
        target_col = "target_default_30d"
        
        X_train, X_test, y_train, y_test = split_and_impute_data(
            df, feature_cols, target_col, test_size=0.3, random_state=42
        )
        
        # Verify split sizes
        # 20 * 0.7 = 14 train, 20 * 0.3 = 6 test
        self.assertEqual(len(X_train), 14)
        self.assertEqual(len(X_test), 6)
        
        # Verify target stratification (y_train has 14 elements, should have 14/20 of the defaults)
        train_defaults = np.sum(y_train == 1)
        test_defaults = np.sum(y_test == 1)
        self.assertGreater(train_defaults, 0)
        self.assertGreater(test_defaults, 0)
        
        # Verify bounded feature value containment
        # monthly_volume < 0 capped at 0
        self.assertTrue((X_train["monthly_volume"] >= 0.0).all())
        self.assertTrue((X_test["monthly_volume"] >= 0.0).all())
        
        # session_regularity capped at 30
        self.assertTrue((X_train["session_regularity"] <= 30).all())
        self.assertTrue((X_test["session_regularity"] <= 30).all())
        
        # Verify missing/infinite/negative values in income are imputed using median
        self.assertFalse(X_train.isnull().any().any())
        self.assertFalse(X_test.isnull().any().any())
        self.assertFalse(np.isinf(X_train).any().any())
        self.assertFalse(np.isinf(X_test).any().any())
        self.assertTrue((X_train["income"] >= 0.0).all())
        self.assertTrue((X_test["income"] >= 0.0).all())

    def test_mathematical_metrics(self) -> None:
        # A1 & A2: Test mathematical correctness of Gini and KS calculations
        # Perfect separation case
        y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1])
        y_prob = np.array([0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9])
        
        roc_auc = calculate_roc_auc(y_true, y_prob)
        gini = calculate_gini(y_true, y_prob)
        ks = calculate_ks(y_true, y_prob)
        
        self.assertEqual(roc_auc, 1.0)
        self.assertEqual(gini, 1.0)
        self.assertEqual(ks, 1.0)
        
        # Overlapping case
        y_true_overlap = np.array([0, 0, 1, 1])
        y_prob_overlap = np.array([0.1, 0.4, 0.35, 0.8])
        
        roc_auc_overlap = calculate_roc_auc(y_true_overlap, y_prob_overlap)
        gini_overlap = calculate_gini(y_true_overlap, y_prob_overlap)
        ks_overlap = calculate_ks(y_true_overlap, y_prob_overlap)
        
        self.assertEqual(roc_auc_overlap, 0.75)
        self.assertEqual(gini_overlap, 0.5)
        self.assertEqual(ks_overlap, 0.5)

    def test_validation_gate_raises_exception(self) -> None:
        # A4: Test validation gate behavior
        # Insert a lot of noise records to train a very poor model
        conn = duckdb.connect(self.db_path)
        conn.execute("DELETE FROM gold.target_construction;")
        
        # Generate random features and targets (poor performance)
        np.random.seed(42)
        records = []
        for i in range(100):
            # Target is randomly assigned
            target = np.random.choice([0, 1])
            records.append((
                f"noise_user_{i}",
                "2025-01-01",
                float(np.random.uniform(100, 5000)),
                int(np.random.randint(1, 31)),
                int(target)
            ))
        conn.executemany("INSERT INTO gold.target_construction VALUES (?, ?, ?, ?, ?)", records)
        conn.close()
        
        # Expect ModelValidationException due to low Gini/KS
        with self.assertRaises(ModelValidationException):
            train_pipeline(
                db_path=self.db_path,
                observation_date="2025-01-01",
                model_output_path=self.output_base,
                experiment_name="test_poor_model_experiment",
                random_state=42
            )

    def test_serialization_and_deserialization(self) -> None:
        # A5: Test serialization format
        # Create and fit a dummy model
        X, y = make_classification(n_samples=100, n_features=3, n_informative=3, n_redundant=0, random_state=42)
        model = xgb.XGBClassifier(random_state=42)
        model.fit(X, y)
        
        # Save model
        save_model(model, self.output_base)
        
        # Verify files exist
        self.assertTrue(os.path.exists(f"{self.output_base}.joblib"))
        self.assertTrue(os.path.exists(f"{self.output_base}.skops"))
        
        # Deserialize joblib model
        loaded_joblib = joblib.load(f"{self.output_base}.joblib")
        preds_joblib = loaded_joblib.predict(X)
        np.testing.assert_array_equal(model.predict(X), preds_joblib)
        
        # Deserialize skops model
        # skops load requires trusted types list in skops >= 0.10
        untrusted = sio.get_untrusted_types(file=f"{self.output_base}.skops")
        loaded_skops = sio.load(f"{self.output_base}.skops", trusted=untrusted)
        preds_skops = loaded_skops.predict(X)
        np.testing.assert_array_equal(model.predict(X), preds_skops)

if __name__ == "__main__":
    unittest.main()
