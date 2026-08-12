# Requirement-to-Test Traceability — CR-003: FastAPI Inference Service

This document maps each analytical requirement (`A1` to `A6`) defined in `requirements.md` to its concrete verification tests in the automated test suite `tests/test_api.py` and the unified verification script `src/api/run_service_verification.py`.

## 🗺️ Traceability Matrix

| Requirement ID | Requirement Name | Test File & Test Cases / Verification Coverage |
|---|---|---|
| **A1** | Dynamic Credit Limit Calculation | - [`tests/test_api.py:TestFastAPIInferenceService.test_predict_policy_decision_tiers`](file:///D:/credit-risk-MELI/tests/test_api.py#L143-L177)<br>- [`src/api/run_service_verification.py`](file:///D:/credit-risk-MELI/src/api/run_service_verification.py#L125-L162) (Low/Med/High risk scenario tests) |
| **A2** | FastAPI Request Handling | - [`tests/test_api.py:TestFastAPIInferenceService.test_predict_success_endpoint`](file:///D:/credit-risk-MELI/tests/test_api.py#L58-L77)<br>- [`tests/test_api.py:TestFastAPIInferenceService.test_health_endpoint_healthy`](file:///D:/credit-risk-MELI/tests/test_api.py#L48-L56) |
| **A3** | Inference Latency SLA | - [`tests/test_api.py:TestFastAPIInferenceService.test_predict_success_endpoint`](file:///D:/credit-risk-MELI/tests/test_api.py#L76) (assert latency_ms < 100.0)<br>- [`src/api/run_service_verification.py`](file:///D:/credit-risk-MELI/src/api/run_service_verification.py#L169-L171) (SLA latency check and warning triggers) |
| **A4** | Input Validation Gate | - [`tests/test_api.py:TestFastAPIInferenceService.test_predict_validation_errors`](file:///D:/credit-risk-MELI/tests/test_api.py#L79-L119) (checks empty user_id, negative volume, bad regularity, negative income)<br>- [`src/api/run_service_verification.py`](file:///D:/credit-risk-MELI/src/api/run_service_verification.py#L164-L175) (Validation failure endpoint query) |
| **A5** | Inference Fallback Policy | - [`tests/test_api.py:TestFastAPIInferenceService.test_predict_fallback_on_missing_model`](file:///D:/credit-risk-MELI/tests/test_api.py#L121-L151)<br>- [`src/api/main.py:predict`](file:///D:/credit-risk-MELI/src/api/main.py#L65-L87) (Robust try-except handling returning PD 0.08, limit 2000, status FALLBACK) |
| **A6** | Service Performance Degradation Warning | - [`src/api/utils.py:LatencyTracker.record_latency`](file:///D:/credit-risk-MELI/src/api/utils.py#L18-L41) (Rolling average warning log if >100.0ms)<br>- [`src/api/main.py:predict`](file:///D:/credit-risk-MELI/src/api/main.py#L89-L97) (SLA threshold check and warning logger) |
