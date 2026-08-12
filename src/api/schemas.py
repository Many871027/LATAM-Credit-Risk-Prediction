from pydantic import BaseModel, Field
from typing import Literal

class InferenceRequest(BaseModel):
    user_id: str = Field(..., min_length=1, description="Unique user identifier.")
    monthly_volume: float = Field(..., ge=0.0, description="Transaction volume in the last 30 days.")
    session_regularity: int = Field(..., ge=0, le=30, description="Active session days in the last 30 days.")
    income: float = Field(..., ge=0.0, description="User monthly income.")

    # Pydantic v2 configuration
    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "usr_99238",
                "monthly_volume": 12500.50,
                "session_regularity": 18,
                "income": 45000.00
            }
        }
    }

class InferenceResponse(BaseModel):
    user_id: str = Field(..., description="Unique user identifier.")
    probability_of_default: float = Field(..., ge=0.0, le=1.0, description="Model-predicted probability of default.")
    credit_limit: float = Field(..., ge=0.0, description="Dynamically allocated credit limit.")
    decision: Literal["APPROVE_LOW_RISK", "APPROVE_MEDIUM_RISK", "REJECT", "FALLBACK_APPROVE"] = Field(
        ..., description="Risk policy decision."
    )
    latency_ms: float = Field(..., description="API request processing time in milliseconds.")
    status: Literal["SUCCESS", "FALLBACK"] = Field(..., description="Execution path status.")
