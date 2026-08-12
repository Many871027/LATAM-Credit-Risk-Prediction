import os
import unittest
import numpy as np
import pandas as pd
import xgboost as xgb
from fastapi.testclient import TestClient

from src.api.main import app
from src.models.registry import save_model

class TestFastAPIInferenceService(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Create a small dummy model with correct feature names for testing
        X = pd.DataFrame(
            [
                [1000.0, 10, 20000.0],
                [5000.0, 20, 50000.0],
                [500.0, 2, 10000.0],
                [20000.0, 30, 150000.0]
            ] * 5,
            columns=["monthly_volume", "session_regularity", "income"]
        )
        y = np.array([0, 0, 1, 0] * 5)
        
        # Train a simple model
        cls.dummy_model = xgb.XGBClassifier(n_estimators=5, max_depth=2, random_state=42)
        cls.dummy_model.fit(X, y)
        
        # Save dummy model in skops format
        cls.model_base_name = "test_api_model"
        save_model(cls.dummy_model, cls.model_base_name)
        
        # Set MODEL_PATH to point to our test model
        cls.orig_model_path = os.environ.get("MODEL_PATH")
        os.environ["MODEL_PATH"] = f"{cls.model_base_name}.skops"

    @classmethod
    def tearDownClass(cls) -> None:
        # Restore environment and cleanup files
        if cls.orig_model_path is not None:
            os.environ["MODEL_PATH"] = cls.orig_model_path
        elif "MODEL_PATH" in os.environ:
            del os.environ["MODEL_PATH"]
            
        for ext in [".joblib", ".skops"]:
            path = f"{cls.model_base_name}{ext}"
            if os.path.exists(path):
                os.remove(path)

    def test_health_endpoint_healthy(self) -> None:
        # R1/A2: Verify GET /health returns HTTP 200 and healthy status when model is loaded
        with TestClient(app) as client:
            response = client.get("/health")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "healthy")
            self.assertTrue(data["model_loaded"])

    def test_predict_success_endpoint(self) -> None:
        # A2: Verify POST /predict successfully returns predictions with valid inputs
        with TestClient(app) as client:
            payload = {
                "user_id": "user_test_123",
                "monthly_volume": 1500.0,
                "session_regularity": 15,
                "income": 30000.0
            }
            response = client.post("/predict", json=payload)
            self.assertEqual(response.status_code, 200)
            
            data = response.json()
            self.assertEqual(data["user_id"], "user_test_123")
            self.assertEqual(data["status"], "SUCCESS")
            self.assertGreaterEqual(data["probability_of_default"], 0.0)
            self.assertLessEqual(data["probability_of_default"], 1.0)
            self.assertIn(data["decision"], ["APPROVE_LOW_RISK", "APPROVE_MEDIUM_RISK", "REJECT"])
            self.assertGreaterEqual(data["credit_limit"], 0.0)
            self.assertLessEqual(data["latency_ms"], 100.0) # Sub-100ms SLA check

    def test_predict_validation_errors(self) -> None:
        # A4: Verify POST /predict returns HTTP 422 on invalid validation inputs
        with TestClient(app) as client:
            # Test empty user_id
            payload_empty_user = {
                "user_id": "",
                "monthly_volume": 1000.0,
                "session_regularity": 10,
                "income": 20000.0
            }
            response = client.post("/predict", json=payload_empty_user)
            self.assertEqual(response.status_code, 422)
            
            # Test negative monthly volume
            payload_neg_vol = {
                "user_id": "usr_1",
                "monthly_volume": -10.0,
                "session_regularity": 10,
                "income": 20000.0
            }
            response = client.post("/predict", json=payload_neg_vol)
            self.assertEqual(response.status_code, 422)
            
            # Test out-of-bounds session regularity (>30)
            payload_session_high = {
                "user_id": "usr_1",
                "monthly_volume": 1000.0,
                "session_regularity": 35,
                "income": 20000.0
            }
            response = client.post("/predict", json=payload_session_high)
            self.assertEqual(response.status_code, 422)
            
            # Test out-of-bounds session regularity (<0)
            payload_session_low = {
                "user_id": "usr_1",
                "monthly_volume": 1000.0,
                "session_regularity": -1,
                "income": 20000.0
            }
            response = client.post("/predict", json=payload_session_low)
            self.assertEqual(response.status_code, 422)
            
            # Test negative income
            payload_neg_income = {
                "user_id": "usr_1",
                "monthly_volume": 1000.0,
                "session_regularity": 10,
                "income": -5000.0
            }
            response = client.post("/predict", json=payload_neg_income)
            self.assertEqual(response.status_code, 422)

    def test_predict_fallback_on_missing_model(self) -> None:
        # A5: Verify fallback procedure when model is missing or fails to load
        # We simulate this by temporarily pointing to a non-existent model file
        orig_path = os.environ.get("MODEL_PATH")
        os.environ["MODEL_PATH"] = "non_existent_model.skops"
        
        try:
            with TestClient(app) as client:
                # 1. Verify health endpoint reports degraded/unloaded model
                health_resp = client.get("/health")
                self.assertEqual(health_resp.status_code, 200)
                health_data = health_resp.json()
                self.assertEqual(health_data["status"], "degraded")
                self.assertFalse(health_data["model_loaded"])
                
                # 2. Verify predict endpoint runs fallback policy
                payload = {
                    "user_id": "usr_fallback_test",
                    "monthly_volume": 1500.0,
                    "session_regularity": 15,
                    "income": 30000.0
                }
                predict_resp = client.post("/predict", json=payload)
                self.assertEqual(predict_resp.status_code, 200)
                
                data = predict_resp.json()
                self.assertEqual(data["user_id"], "usr_fallback_test")
                self.assertEqual(data["probability_of_default"], 0.08)
                self.assertEqual(data["credit_limit"], 2000.0)
                self.assertEqual(data["decision"], "FALLBACK_APPROVE")
                self.assertEqual(data["status"], "FALLBACK")
                self.assertLessEqual(data["latency_ms"], 100.0)
        finally:
            if orig_path is not None:
                os.environ["MODEL_PATH"] = orig_path
            else:
                os.environ.pop("MODEL_PATH", None)

    def test_predict_policy_decision_tiers(self) -> None:
        # A1: Test the individual credit decision assignment rules mapping PD & income to limit & decision
        from src.api.engine import calculate_credit_decision
        
        # Scenario 1: PD > 0.10 -> Reject, Limit = 0
        limit, dec = calculate_credit_decision(pd=0.15, income=50000.0)
        self.assertEqual(limit, 0.0)
        self.assertEqual(dec, "REJECT")
        
        # Scenario 2: 0.04 < PD <= 0.10 -> Medium Risk. Limit = min(max(0.10 * income, 2000), 25000)
        # Income = 10000 -> 10% = 1000. max(1000, 2000) = 2000. min(2000, 25000) = 2000.
        limit, dec = calculate_credit_decision(pd=0.08, income=10000.0)
        self.assertEqual(limit, 2000.0)
        self.assertEqual(dec, "APPROVE_MEDIUM_RISK")
        
        # Income = 300000 -> 10% = 30000. max(30000, 2000) = 30000. min(30000, 25000) = 25000.
        limit, dec = calculate_credit_decision(pd=0.06, income=300000.0)
        self.assertEqual(limit, 25000.0)
        self.assertEqual(dec, "APPROVE_MEDIUM_RISK")
        
        # Scenario 3: PD <= 0.04 -> Low Risk. Limit = min(max(0.25 * income, 5000), 100000)
        # Income = 10000 -> 25% = 2500. max(2500, 5000) = 5000. min(5000, 100000) = 5000.
        limit, dec = calculate_credit_decision(pd=0.02, income=10000.0)
        self.assertEqual(limit, 5000.0)
        self.assertEqual(dec, "APPROVE_LOW_RISK")
        
        # Income = 500000 -> 25% = 125000. max(125000, 5000) = 125000. min(125000, 100000) = 100000.
        limit, dec = calculate_credit_decision(pd=0.01, income=500000.0)
        self.assertEqual(limit, 100000.0)
        self.assertEqual(dec, "APPROVE_LOW_RISK")

if __name__ == "__main__":
    unittest.main()
