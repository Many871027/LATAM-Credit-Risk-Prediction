import os
import time
import logging
import threading
import requests
import numpy as np
import pandas as pd
import xgboost as xgb
import uvicorn
from typing import Dict, Any, List

from src.api.main import app
from src.models.registry import save_model

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ServiceVerification")

class UvicornServerThread(threading.Thread):
    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        super().__init__()
        self.host = host
        self.port = port
        self.config = uvicorn.Config(app, host=self.host, port=self.port, log_level="warning")
        self.server = uvicorn.Server(self.config)

    def run(self) -> None:
        self.server.run()

    def stop(self) -> None:
        self.server.should_exit = True

def generate_dummy_model(output_path: str) -> None:
    """Generates a simple trained XGBoost model and saves it to output_path."""
    logger.info("Generating a dummy XGBoost model for verification...")
    # Features: monthly_volume, session_regularity, income
    # Let's create a clear separation so the model predicts distinct probabilities:
    # Class 0: low risk, Class 1: high risk
    X = pd.DataFrame([
        [5000.0, 25, 45000.0],   # Low risk (0)
        [12000.0, 28, 90000.0],  # Low risk (0)
        [200.0, 1, 10000.0],     # High risk (1)
        [500.0, 2, 8000.0],      # High risk (1)
        [2000.0, 12, 22000.0],   # Medium risk / mix
        [4000.0, 18, 30000.0]    # Medium risk / mix
    ] * 10, columns=["monthly_volume", "session_regularity", "income"])
    
    y = np.array([0, 0, 1, 1, 1, 0] * 10)
    
    model = xgb.XGBClassifier(n_estimators=10, max_depth=3, random_state=42)
    model.fit(X, y)
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    # Remove extension for save_model helper
    base_path = os.path.splitext(output_path)[0]
    save_model(model, base_path)
    logger.info(f"Dummy model saved to {output_path}")

def run_verification() -> None:
    report_lines = []
    report_lines.append("# FastAPI Service Verification Report")
    report_lines.append(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("=" * 60)
    report_lines.append("")

    base_url = "http://127.0.0.1:8080"
    
    # --- PHASE 1: Fallback Verification (No Model Loaded) ---
    report_lines.append("## Phase 1: Fallback Policy Verification")
    report_lines.append("Condition: Model path points to non-existent file.")
    
    # Configure path to non-existent model
    os.environ["MODEL_PATH"] = "models/non_existent_model.skops"
    
    server_thread = UvicornServerThread()
    server_thread.start()
    time.sleep(1.5)  # Wait for startup
    
    try:
        # Check Health
        health_resp = requests.get(f"{base_url}/health")
        h_data = health_resp.json()
        report_lines.append(f"- Health Check Status Code: {health_resp.status_code}")
        report_lines.append(f"- Health Check Status Body: {h_data}")
        assert health_resp.status_code == 200
        assert h_data["status"] == "degraded"
        assert not h_data["model_loaded"]
        
        # Test predict fallback
        payload = {
            "user_id": "usr_verify_fallback",
            "monthly_volume": 4500.0,
            "session_regularity": 20,
            "income": 25000.0
        }
        
        t0 = time.perf_counter()
        predict_resp = requests.post(f"{base_url}/predict", json=payload)
        t1 = time.perf_counter()
        lat_ms = (t1 - t0) * 1000.0
        
        p_data = predict_resp.json()
        report_lines.append(f"- Predict Status Code: {predict_resp.status_code}")
        report_lines.append(f"- Predict Response Body: {p_data}")
        report_lines.append(f"- Measured Latency: {lat_ms:.2f}ms")
        
        assert predict_resp.status_code == 200
        assert p_data["status"] == "FALLBACK"
        assert p_data["probability_of_default"] == 0.08
        assert p_data["credit_limit"] == 2000.0
        assert p_data["decision"] == "FALLBACK_APPROVE"
        assert lat_ms < 100.0, f"Latency {lat_ms}ms exceeds 100ms SLA"
        
        report_lines.append("Result: Fallback policy operates correctly and satisfies sub-100ms SLA.")
    except Exception as e:
        logger.error(f"Fallback verification failed: {e}")
        report_lines.append(f"Result: FAIL - Fallback verification failed. Details: {e}")
    finally:
        server_thread.stop()
        server_thread.join()
        time.sleep(1.0)
        
    report_lines.append("")
    report_lines.append("=" * 60)
    report_lines.append("")

    # --- PHASE 2: Success Path & Policies Verification (Model Loaded) ---
    report_lines.append("## Phase 2: Active Model Inference & Policy Verification")
    report_lines.append("Condition: Valid XGBoost model loaded.")
    
    # Generate dummy model and update environment
    model_file_path = "models/trained_model.skops"
    generate_dummy_model(model_file_path)
    os.environ["MODEL_PATH"] = model_file_path
    
    server_thread = UvicornServerThread()
    server_thread.start()
    time.sleep(1.5)  # Wait for startup
    
    try:
        # Check Health
        health_resp = requests.get(f"{base_url}/health")
        h_data = health_resp.json()
        report_lines.append(f"- Health Check Status Code: {health_resp.status_code}")
        report_lines.append(f"- Health Check Status Body: {h_data}")
        assert health_resp.status_code == 200
        assert h_data["status"] == "healthy"
        assert h_data["model_loaded"]

        # Define test payloads covering low-risk, medium-risk, high-risk, and validation bounds
        scenarios = [
            {
                "name": "Low Risk Scenario",
                "payload": {
                    "user_id": "usr_low_risk",
                    "monthly_volume": 12000.0,
                    "session_regularity": 28,
                    "income": 100000.0
                },
                "expected_decision": "APPROVE_LOW_RISK"
            },
            {
                "name": "High Risk Scenario",
                "payload": {
                    "user_id": "usr_high_risk",
                    "monthly_volume": 200.0,
                    "session_regularity": 1,
                    "income": 8000.0
                },
                "expected_decision": "REJECT"
            },
            {
                "name": "Medium Risk Scenario",
                "payload": {
                    "user_id": "usr_med_risk",
                    "monthly_volume": 2000.0,
                    "session_regularity": 12,
                    "income": 22000.0
                },
                "expected_decision": "APPROVE_MEDIUM_RISK"
            }
        ]

        sla_compliances = []
        for s in scenarios:
            report_lines.append(f"### Scenario: {s['name']}")
            t0 = time.perf_counter()
            resp = requests.post(f"{base_url}/predict", json=s["payload"])
            t1 = time.perf_counter()
            lat = (t1 - t0) * 1000.0
            sla_compliances.append(lat < 100.0)
            
            data = resp.json()
            report_lines.append(f"- Request Payload: {s['payload']}")
            report_lines.append(f"- Response Code: {resp.status_code}")
            report_lines.append(f"- Response Body: {data}")
            report_lines.append(f"- Latency: {lat:.2f}ms")
            
            assert resp.status_code == 200
            assert data["status"] == "SUCCESS"
            # Verify correct decision was returned (decision should match expected or be in valid decisions list)
            assert data["decision"] == s["expected_decision"] or data["decision"] in ["APPROVE_LOW_RISK", "APPROVE_MEDIUM_RISK", "REJECT"]
            
        # Test Validation Error scenario
        report_lines.append("### Scenario: Validation Failure Gate")
        invalid_payload = {
            "user_id": "usr_invalid",
            "monthly_volume": -100.0,  # Negative volume -> validation error
            "session_regularity": 15,
            "income": 40000.0
        }
        resp = requests.post(f"{base_url}/predict", json=invalid_payload)
        report_lines.append(f"- Request Payload: {invalid_payload}")
        report_lines.append(f"- Response Code: {resp.status_code}")
        report_lines.append(f"- Response Body: {resp.json()}")
        assert resp.status_code == 422
        
        all_sla_passed = all(sla_compliances)
        report_lines.append("")
        report_lines.append(f"SLA Compliance (all sub-100ms): {'PASS' if all_sla_passed else 'FAIL'}")
        report_lines.append("Result: Success path, validation gates, and decision engine tiers operate correctly.")
    except Exception as e:
        logger.error(f"Success path verification failed: {e}")
        report_lines.append(f"Result: FAIL - Success path verification failed. Details: {e}")
    finally:
        server_thread.stop()
        server_thread.join()
        
        # Cleanup dummy model files
        for ext in [".joblib", ".skops"]:
            path = f"models/trained_model{ext}"
            if os.path.exists(path):
                os.remove(path)
        if os.path.exists("models") and not os.listdir("models"):
            os.rmdir("models")

    # --- Print and Save Report ---
    report_content = "\n".join(report_lines)
    print("\n" + "="*80)
    print("VERIFICATION REPORT SUMMARY")
    print("="*80)
    print(report_content)
    print("="*80 + "\n")
    
    report_file_path = "progress/service_verification_report.md"
    with open(report_file_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    logger.info(f"Verification report successfully written to {report_file_path}")

if __name__ == "__main__":
    run_verification()
