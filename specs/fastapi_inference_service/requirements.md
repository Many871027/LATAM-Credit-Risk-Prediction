# Analytical Requirements Specification — CR-003: FastAPI Inference Service

This document details the analytical requirements for the real-time inference service feature **CR-003 (fastapi_inference_service)**.

## 📊 Business Acceptance Criteria Mapping
The business acceptance criteria defined in `feature_list.json` are mapped to the analytical requirements below:
- **Criterion 1 (Async /predict Endpoint & Pydantic Validation):** Covered by **A2** (FastAPI Request Handling) and **A4** (Input Validation Gate).
- **Criterion 2 (Sub-100ms Response SLA):** Covered by **A3** (Inference Latency SLA).
- **Criterion 3 (Dynamic Credit Limit Allocation):** Covered by **A1** (Dynamic Credit Limit Calculation).
- **Criterion 4 (Fallback Mechanisms):** Covered by **A5** (Inference Fallback Policy).

---

## 🔤 Analytical Requirements (EARS-BI Notation)

### 1. Ubiquitous (Base & Immutable Metrics)

*   **A1: Dynamic Credit Limit Calculation**
    *   *Requirement*: The analytical layer SHALL calculate the dynamic credit limit using the risk policy piecewise function over the predicted probability of default (PD) and user monthly income.
    *   *Formulation*:
        *   IF $PD > 0.10$ (High Risk), the credit limit SHALL be set to $0$ (Rejected).
        *   IF $0.04 < PD \le 0.10$ (Medium Risk), the credit limit SHALL be set to $\min(\max(0.10 \times \text{income}, 2000), 25000)$.
        *   IF $PD \le 0.04$ (Low Risk), the credit limit SHALL be set to $\min(\max(0.25 \times \text{income}, 5000), 100000)$.
    *   *Grain*: Individual prediction query level.

### 2. Event-Driven (ETL / Ingestion Strategies)

*   **A2: FastAPI Request Handling**
    *   *Requirement*: WHEN an HTTP POST request is received at the `/predict` endpoint, the inference system SHALL resolve user credit predictions by invoking the serialized XGBoost model, calculating the probability of default (PD), and applying the dynamic credit limit policy.

*   **A3: Inference Latency SLA**
    *   *Requirement*: WHEN an HTTP POST request is received at the `/predict` endpoint, the inference system SHALL return the calculated results within a sub-100ms response SLA.

### 3. Unwanted Behavior (Data Governance & Quality)

*   **A4: Input Validation Gate**
    *   *Requirement*: IF any input attribute in the `/predict` request payload violates the defined Pydantic constraints or contains NULL values in primary fields, the system SHALL immediately reject the request and return an HTTP 422 validation response.

*   **A5: Inference Fallback Policy**
    *   *Requirement*: IF model loading fails, model serialization is corrupted, or model inference throws an unexpected exception, the system SHALL execute a fallback procedure returning a default probability of default (PD) of 0.08 and a safe credit limit of 2000.

### 4. State-Driven (AI Alerting Thresholds)

*   **A6: Service Performance Degradation Warning**
    *   *Requirement*: WHILE the average endpoint latency exceeds 100ms over a rolling 1-minute window, the AI agent SHALL log a high-priority performance warning to the application log.

---

## 📥 Input & Output Data Definitions

### Inputs (FastAPI /predict Payload)
1.  **`user_id`** (String): Unique identifier of the user requesting credit evaluation. Must not be empty.
2.  **`monthly_volume`** (Float): User transaction volume in the last 30 days. Must be non-negative.
3.  **`session_regularity`** (Integer): Number of active session days in the last 30 days. Must be between 0 and 30 inclusive.
4.  **`income`** (Float): Monthly income of the user. Must be non-negative.

### Outputs (FastAPI /predict Response)
1.  **`user_id`** (String): Unique identifier of the user.
2.  **`probability_of_default`** (Float): Model probability score ($0.0 \le PD \le 1.0$).
3.  **`credit_limit`** (Float): Allocated limit based on risk tiers ($0.0 \le \text{limit} \le 100000.0$).
4.  **`decision`** (String): Approval status (`"APPROVE_LOW_RISK"`, `"APPROVE_MEDIUM_RISK"`, `"REJECT"`, or `"FALLBACK_APPROVE"`).
5.  **`latency_ms`** (Float): Time taken to process the query.
6.  **`status`** (String): Processing status (`"SUCCESS"` or `"FALLBACK"`).
