"""FastAPI application for the educational fraud-monitoring dashboard."""

from datetime import datetime, timezone
from pathlib import Path
import secrets
from typing import Literal

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from database import database


ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "model" / "fraud_model.joblib"
TEMPLATES_PATH = ROOT / "templates"
STATIC_PATH = ROOT / "static"


def load_model_artifact() -> dict:
    if not MODEL_PATH.exists():
        raise RuntimeError(
            "Trained model not found. Run 'python generate_dataset.py' and "
            "'python train_model.py' before starting the application."
        )
    artifact = joblib.load(MODEL_PATH)
    if not isinstance(artifact, dict) or not {
        "model",
        "feature_columns",
        "metrics",
    }.issubset(artifact):
        raise RuntimeError("The model file has an invalid format. Retrain it with train_model.py.")
    return artifact


MODEL_ARTIFACT = load_model_artifact()
CLASSIFIER = MODEL_ARTIFACT["model"]
FEATURE_COLUMNS = MODEL_ARTIFACT["feature_columns"]

app = FastAPI(
    title="Real-Time Fraud Detection System",
    description="Educational transaction risk scoring and monitoring API.",
    version="1.0.0",
)
app.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")


class TransactionInput(BaseModel):
    amount: float = Field(gt=0, le=10_000_000)
    transaction_time: str
    device_id: str = Field(min_length=1, max_length=64)
    is_new_device: bool
    location: str = Field(min_length=1, max_length=120)
    transactions_last_5min: int = Field(ge=0, le=100)
    amount_last_5min: float = Field(ge=0, le=10_000_000)
    average_transaction_amount: float = Field(gt=0, le=10_000_000)
    distance_from_usual_location: float = Field(ge=0, le=20_000)

    @field_validator("transaction_time")
    @classmethod
    def validate_transaction_time(cls, value: str) -> str:
        try:
            datetime.strptime(value, "%H:%M")
        except ValueError as error:
            raise ValueError("Transaction time must use 24-hour HH:MM format.") from error
        return value

    @field_validator("device_id", "location")
    @classmethod
    def validate_nonblank_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value


def assess_probability(probability: float) -> tuple[str, str, str]:
    if probability < 0.30:
        return "LOW", "APPROVED", "SUCCESS"
    if probability <= 0.70:
        return "MEDIUM", "REVIEW", "PENDING"
    return "HIGH", "BLOCKED", "DECLINED"


@app.on_event("startup")
def on_startup() -> None:
    database.initialize_database()


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(TEMPLATES_PATH / "index.html")


@app.post("/api/predict")
def predict_transaction(payload: TransactionInput) -> dict:
    values = payload.model_dump()
    hour = datetime.strptime(values["transaction_time"], "%H:%M").hour
    features = {
        "amount": values["amount"],
        "hour": hour,
        "is_new_device": int(values["is_new_device"]),
        "location_change": int(values["distance_from_usual_location"] >= 100),
        "transactions_last_5min": values["transactions_last_5min"],
        "amount_last_5min": values["amount_last_5min"],
        "average_transaction_amount": values["average_transaction_amount"],
        "distance_from_usual_location": values["distance_from_usual_location"],
    }
    try:
        feature_frame = pd.DataFrame([[features[name] for name in FEATURE_COLUMNS]], columns=FEATURE_COLUMNS)
        probability = float(CLASSIFIER.predict_proba(feature_frame)[0][1])
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise HTTPException(status_code=500, detail="Unable to score this transaction.") from error

    risk_level, decision, status = assess_probability(probability)
    transaction_id = f"TXN-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{secrets.token_hex(3).upper()}"
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = {
        **values,
        "transaction_id": transaction_id,
        "is_new_device": int(values["is_new_device"]),
        "fraud_probability": round(probability, 6),
        "risk_level": risk_level,
        "decision": decision,
        "status": status,
        "created_at": created_at,
    }
    try:
        database.save_transaction(record)
    except Exception as error:
        raise HTTPException(status_code=500, detail="Unable to save the transaction.") from error

    return {
        "transaction_id": transaction_id,
        "fraud_probability": round(probability, 6),
        "risk_level": risk_level,
        "decision": decision,
        "status": status,
        "created_at": created_at,
    }


@app.get("/api/transactions")
def list_transactions(limit: int = 50) -> list[dict]:
    if not 1 <= limit <= 10_000:
        raise HTTPException(status_code=422, detail="Limit must be between 1 and 10000.")
    return database.get_recent_transactions(limit)


@app.delete("/api/transactions")
def clear_transaction_history() -> dict[str, int | str]:
    deleted_count = database.clear_transactions()
    return {"message": "Transaction history cleared.", "deleted_count": deleted_count}


@app.get("/api/stats")
def dashboard_stats() -> dict:
    return database.get_dashboard_stats()


@app.get("/api/model-metrics")
def model_metrics() -> dict:
    return {
        "model_name": MODEL_ARTIFACT.get("model_name", "Random Forest Classifier"),
        "training_rows": MODEL_ARTIFACT.get("training_rows", 0),
        **MODEL_ARTIFACT["metrics"],
    }