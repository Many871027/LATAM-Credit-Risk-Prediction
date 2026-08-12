# Credit Risk Modeling Framework — Mercado Pago (MELI)

Welcome to the **Credit Risk Modeling Framework** for Mercado Pago. This project simulates a production-grade credit risk pipeline designed to evaluate borrower creditworthiness, train predictive scoring models, make real-time decisions, and monitor system health.

The project is built around a **Medallion Data Architecture** using **DuckDB**, orchestrated with **Prefect**, trained using **XGBoost**, and served via **FastAPI**.

---

## 🏗️ System Architecture

```
                                    +-----------------------+
                                    |    Raw Source Data    |
                                    +-----------+-----------+
                                                | Ingestion (Prefect)
                                                v
+---------------------------------------------------------------------------------------+
| DUCKDB ANALYTICAL WAREHOUSE                                                           |
|                                                                                       |
|   +-----------------------+       +-----------------------+   +-------------------+   |
|   |     Bronze Layer      | ----> |     Silver Layer      | ->|    Gold Layer     |   |
|   | (Append-Only/Raw/Null)| Cleaning & Deduplication (SQL)|   | (Features/Target) |   |
|   +-----------------------+       +-----------------------+   +---------+---------+   |
+-------------------------------------------------------------------------|-------------+
                                                                          | Training
                                                                          v
                                                             +-----------------------+
                                                             |   XGBoost Scoring     |
                                                             |  (Gini/KS Evaluation) |
                                                             +-----------+-----------+
                                                                         | Serialization
                                                                         v
                                                             +-----------------------+
                                                             |    FastAPI Service    |
                                                             | (Real-Time Inference) |
                                                             +-----------------------+
```

### 1. Medallion Data Pipeline (`DuckDB` & `Prefect`)
- **Bronze Layer:** Raw data ingestion preserving all duplicates, null keys, and format irregularities.
- **Silver Layer:** Standardizes schema formats (parsing slash/dash dates), applies carrier normalization, filters invalid identifiers, and deduplicates records using rolling SQL window ranking.
- **Gold Layer:** Builds aggregation features (e.g. 30-day transactional volume, session activity calendar count) and constructs the model target variable `target_default_30d` (binary indicator for default >30 DPD within 12 months).

### 2. Model Training Pipeline (`XGBoost`)
- Consumes aggregated user profiles from the Gold layer.
- Trains a gradient boosting risk classifier with strict evaluation metrics:
  - **Gini Index >= 0.65** (ROC-AUC >= 0.825)
  - **Kolmogorov-Smirnov (KS) Statistic >= 45%**
- Serializes model checkpoints using `skops` / `joblib`.

### 3. Real-Time Scoring API (`FastAPI`)
- Serving predictions asynchronously under a strict **sub-100ms** latency SLA.
- Strictly validates inputs using Pydantic schemas.
- Assigns dynamic credit limits based on calculated default probability and average monthly income.
- Integrates defensive fallback logic (returning safe cohort-level default scores if data is missing or inference fails).

### 4. MLOps Monitoring (`MLflow`)
- Computes **Population Stability Index (PSI)** weekly to detect prediction and feature drift.
- Registers custom MLflow scorers to evaluate dialogue responses and safety policies.

---

## 🚀 Getting Started

This repository leverages [uv](https://github.com/astral-sh/uv) for fast, deterministic Python environment and package management.

### Prerequisites

Ensure you have Python 3.9+ and `uv` installed.

### Setup and Installation

1.  **Clone the repository** and navigate to the project directory:
    ```bash
    cd D:/credit-risk-MELI
    ```
2.  **Initialize the virtual environment:**
    ```bash
    uv venv venv
    ```
3.  **Activate the virtual environment:**
    - **Windows (PowerShell):**
      ```powershell
      . venv/Scripts/activate.ps1
      ```
    - **Linux / macOS:**
      ```bash
      source venv/bin/activate
      ```
4.  **Install dependencies:**
    ```bash
    uv pip install -r requirements.txt --python venv/Scripts/python.exe
    ```

---

## 🧪 Verification and Testing

The project includes an automated test harness designed to guarantee code quality and traceability of analytical specifications.

To verify the installation and run all tests, execute the verification script:
```bash
bash ./init.sh
```

All analytical requirements are documented under `specs/` using EARS-BI syntax and verified by tests inside `tests/`.

---

## 🛠️ Spec-Driven Development (SDD) Workflow

This project enforces strict **Spec-Driven Development**. Any feature addition must traverse the following phases:

```
pending → [spec_author] → spec_ready → ⏸ HUMAN APPROVAL → in_progress → [implementer → reviewer] → done
```

- Specifications reside in `specs/<feature_name>/` containing `requirements.md`, `design.md`, and `tasks.md`.
- No code in `src/` or `tests/` is written before the spec secures human approval.
