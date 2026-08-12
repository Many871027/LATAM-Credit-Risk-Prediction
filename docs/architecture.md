# Project Architecture — Credit Risk ML Framework

This document outlines the architectural standards and structural layout of the Credit Risk Machine Learning project. All code must adhere to these patterns.

## 🏢 Layered Layout

The repository is structured into distinct layers to separate concerns:

```
src/
├── data/          # Feature engineering, database ingestion, ETL SQL templates
├── models/        # Model definition (XGBoost/LightGBM), serialization, inference engine
├── api/           # FastAPI endpoints, async routing, WebSockets diagnostic handler
└── monitoring/    # MLflow integration, population stability index (PSI) computation, drift detection
```

### 1. Data Layer (`src/data/`)
- Contains SQL extraction templates for BigQuery.
- Processes transactional events incrementally to generate features.
- Operates under strict EARS requirements to ensure data quality (deduplication, type safety, null handling).

### 2. Model Layer (`src/models/`)
- Encapsulates model training, validation, and serialization.
- Implements traditional credit risk metrics: Gini index, Kolmogorov-Smirnov (KS) statistic, and confusion matrices.
- Optimizes inference engines for sub-100ms response times.

### 3. API Layer (`src/api/`)
- Async-first HTTP endpoints via FastAPI.
- WebSockets for interactive diagnostic queries.
- Read-only tools validation (`SQLToolExecutor`) preventing destructive operations.

### 4. Monitoring Layer (`src/monitoring/`)
- Tracks model performance and data drift.
- Custom scorers registered in MLflow to validate LLM outputs (fidelity, hallucination checks).

---

## ⚡ Async-First Principles

- All database queries and external integrations (Vertex AI, Meta API) must use non-blocking asynchronous calls.
- WebSockets are used for bidirectional, real-time diagnostic communications.
- Background tasks (such as retraining or drift computation) must be handled asynchronously using FastAPI's background tasks or task queues.

---

## 📊 Observability

- Comprehensive telemetry tracking API latency, prediction distributions, and request payload statistics.
- Direct output tracing using structured logging.
- Population Stability Index (PSI) computed weekly to monitor feature/prediction drift.
