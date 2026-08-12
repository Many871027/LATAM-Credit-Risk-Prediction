import os
import time
import logging
import traceback
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
import skops.io as sio
import pandas as pd

from src.api.schemas import InferenceRequest, InferenceResponse
from src.api.engine import calculate_credit_decision
from src.api.utils import LatencyTracker

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fastapi_inference_service")

# Initialize latency tracker
latency_tracker = LatencyTracker()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load the model securely
    model_path = os.getenv("MODEL_PATH", "models/trained_model.skops")
    logger.info(f"Startup: Loading model from path: {model_path}")
    try:
        # Load securely by defining trusted types to prevent pickle vulnerabilities
        app.state.model = sio.load(
            model_path,
            trusted=[
                "xgboost.sklearn.XGBClassifier",
                "xgboost.core.Booster",
                "numpy.dtype",
                "numpy.core.multiarray._reconstruct"
            ]
        )
        logger.info("Startup: Model loaded successfully.")
    except Exception as e:
        logger.error(f"Startup error: Model loading failed. Falling back to default scoring. Details: {e}")
        app.state.model = None
    
    yield
    # Shutdown: Clean up resources
    app.state.model = None
    logger.info("Shutdown: Model resources released.")

app = FastAPI(
    title="Credit Risk Inference Service",
    description="Real-time inference API for scoring risk and dynamic credit limit allocation.",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/health", status_code=status.HTTP_200_OK)
def health() -> dict:
    """
    GET /health endpoint.
    Returns status indicator of the application and model state.
    """
    model_loaded = getattr(app.state, "model", None) is not None
    return {
        "status": "healthy" if model_loaded else "degraded",
        "model_loaded": model_loaded
    }

@app.post("/predict", response_model=InferenceResponse, status_code=status.HTTP_200_OK)
async def predict(request: InferenceRequest) -> InferenceResponse:
    """
    POST /predict endpoint.
    Resolves user credit predictions, applies dynamic risk policies, and implements robust fallback paths.
    """
    t_start = time.perf_counter()
    status_val = "SUCCESS"
    pd_val = 0.08
    credit_limit = 2000.0
    decision = "FALLBACK_APPROVE"
    
    try:
        model = getattr(app.state, "model", None)
        if model is None:
            raise RuntimeError("Model is not loaded in application state")
        
        # Prepare input data matching feature columns expected by the model
        X = pd.DataFrame(
            [[request.monthly_volume, request.session_regularity, request.income]],
            columns=["monthly_volume", "session_regularity", "income"]
        )
        
        # Compute predicted Probability of Default (PD)
        probs = model.predict_proba(X)
        pd_val = float(probs[0, 1])
        
        # Apply risk policies to calculate decision and limit
        credit_limit, decision = calculate_credit_decision(pd_val, request.income)
        
    except Exception as e:
        logger.error(f"Prediction fallback triggered. Failure details: {e}")
        logger.error(traceback.format_exc())
        status_val = "FALLBACK"
        pd_val = 0.08
        credit_limit = 2000.0
        decision = "FALLBACK_APPROVE"
        
    t_end = time.perf_counter()
    latency_ms = (t_end - t_start) * 1000.0
    
    # Record and update rolling average latency
    latency_tracker.record_latency(latency_ms)
    
    # SLA enforcement check (A3)
    if latency_ms > 100.0:
        logger.warning(
            f"[SLA WARNING] Request took {latency_ms:.2f}ms to process, which exceeds the sub-100ms SLA."
        )
        
    return InferenceResponse(
        user_id=request.user_id,
        probability_of_default=pd_val,
        credit_limit=credit_limit,
        decision=decision,
        latency_ms=latency_ms,
        status=status_val
    )
