# Implementation Tasks Checklist — CR-003: FastAPI Inference Service

This document lists the step-by-step implementation tasks required to build the real-time inference service using FastAPI, Pydantic, and secure Skops model deserialization.

---

## 📋 Tasks Checklist

### Phase 1: Environment Setup & Directory Initialization

- [x] **Task 1: Setup Dependencies and Directory Structure**
      Create the `src/api` directory if it does not exist. Ensure that `fastapi`, `uvicorn`, `pydantic`, `joblib`, and `skops` are declared in the project's `requirements.txt` and installed in the virtual environment. Define empty Python files `src/api/main.py`, `src/api/schemas.py`, `src/api/engine.py`, and `src/api/utils.py`.
      *Requirement Mapping:* None (Infrastructure / Environment Setup)

### Phase 2: Input/Output Schemas & Risk Policy Logic

- [x] **Task 2: Implement Pydantic Input/Output Schemas**
      Write the request validation schema `InferenceRequest` and response schema `InferenceResponse` in `src/api/schemas.py` according to the defined technical design. Include validation bounds for feature fields (`monthly_volume` >= 0, 0 <= `session_regularity` <= 30, and `income` >= 0).
      *Requirement Mapping:* `A2`, `A4`

- [x] **Task 3: Implement Risk Decision Engine**
      Write a function `calculate_credit_decision(pd: float, income: float) -> Tuple[float, str]` in `src/api/engine.py` that implements the dynamic credit policy piecewise logic:
      1. IF $PD > 0.10$, return credit limit = 0 and decision = "REJECT".
      2. IF $0.04 < PD \le 0.10$, return credit limit = $\min(\max(0.10 \times \text{income}, 2000), 25000)$ and decision = "APPROVE_MEDIUM_RISK".
      3. IF $PD \le 0.04$, return credit limit = $\min(\max(0.25 \times \text{income}, 5000), 100000)$ and decision = "APPROVE_LOW_RISK".
      *Requirement Mapping:* `A1`

### Phase 3: Web Service Setup & Endpoints

- [x] **Task 4: Implement Secure Model Load Lifespan**
      Implement the lifespan context manager in `src/api/main.py` that loads the pre-trained XGBoost model from the path stored in the `MODEL_PATH` environment variable (default: `models/trained_model.skops`). The model must be loaded securely using `skops.io.load()` with the list of trusted types specified in the technical design to prevent arbitrary code execution.
      *Requirement Mapping:* `A5`

- [x] **Task 5: Implement API Endpoints with SLA Control & Fallbacks**
      In `src/api/main.py`, implement:
      1. A GET `/health` endpoint that returns a status indicator of the application and model state.
      2. An async POST `/predict` endpoint that takes `InferenceRequest`, measures latency using `time.perf_counter()`, and runs the inference pipeline.
      3. A try-except fallback block in `/predict` that intercepts model prediction or loading errors, logs the traceback, and returns a safe default payload ($PD=0.08$, limit=$2000, decision="FALLBACK_APPROVE", status="FALLBACK").
      4. A validation check that prints a warning to logs if the calculated latency exceeds the 100ms SLA.
      *Requirement Mapping:* `A2`, `A3`, `A5`, `A6`

### Phase 4: Automated Testing & Verification

- [x] **Task 6: Implement Automated Test Suite**
      Create a test file `tests/test_api.py`. Using FastAPI's `TestClient`, implement unit and integration tests verifying:
      1. GET `/health` returns HTTP 200 and a healthy status.
      2. POST `/predict` returns correct predictions, credit limits, and decisions for normal inputs.
      3. POST `/predict` returns HTTP 422 error for invalid payloads (out-of-bounds or negative feature values).
      4. POST `/predict` successfully falls back to safe default parameters when the model fails or is missing.
      5. The endpoint satisfies the sub-100ms response SLA.
      Run all tests using the project test command.
      *Requirement Mapping:* `A1` to `A6`

### Phase 5: Unified Pipeline Verification Script

- [x] **Task 7: Create Unified Service Execution and Verification Script**
      Create a single, unified Python script `src/api/run_service_verification.py` that aggregates and executes all operations, queries, and report generation procedures defined in the preceding tasks of this specification. Specifically, the script must:
      1. Spin up the FastAPI application locally using Uvicorn in a background process or thread.
      2. Construct and send multiple HTTP POST requests to `/predict` (covering low-risk, medium-risk, high-risk, validation failures, and fallback scenarios).
      3. Measure and print the response times to confirm the sub-100ms SLA.
      4. Collect and aggregate the responses into a formatted text report showing endpoint status, prediction accuracy, and SLA compliance.
      5. Terminate the background Uvicorn server gracefully upon execution completion.
      *Requirement Mapping:* All (`A1` - `A6`)
