"""Train and evaluate the transaction risk classifier."""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split


ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "transactions.csv"
MODEL_PATH = ROOT / "model" / "fraud_model.joblib"
FEATURE_COLUMNS = [
    "amount",
    "hour",
    "is_new_device",
    "location_change",
    "transactions_last_5min",
    "amount_last_5min",
    "average_transaction_amount",
    "distance_from_usual_location",
]


def train_model() -> dict:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found at {DATA_PATH}. Run python generate_dataset.py first."
        )

    dataset = pd.read_csv(DATA_PATH)
    missing_columns = set(FEATURE_COLUMNS + ["fraud"]) - set(dataset.columns)
    if missing_columns:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing_columns)}")
    if len(dataset) < 100:
        raise ValueError("At least 100 rows are required to train the model.")

    features = dataset[FEATURE_COLUMNS]
    labels = dataset["fraud"].astype(int)
    x_train, x_test, y_train, y_test = train_test_split(
        features,
        labels,
        test_size=0.2,
        random_state=42,
        stratify=labels,
    )
    classifier = RandomForestClassifier(
        n_estimators=180,
        max_depth=12,
        min_samples_leaf=4,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=-1,
    )
    classifier.fit(x_train, y_train)
    predictions = classifier.predict(x_test)
    metrics = {
        "accuracy": round(float(accuracy_score(y_test, predictions)), 4),
        "precision": round(float(precision_score(y_test, predictions, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, predictions, zero_division=0)), 4),
        "f1_score": round(float(f1_score(y_test, predictions, zero_division=0)), 4),
        "confusion_matrix": confusion_matrix(y_test, predictions, labels=[0, 1]).tolist(),
        "test_rows": int(len(y_test)),
        "training_rows": int(len(y_train)),
    }
    artifact = {
        "model": classifier,
        "feature_columns": FEATURE_COLUMNS,
        "metrics": metrics,
        "training_rows": int(len(dataset)),
        "model_name": "Random Forest Classifier",
    }
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, MODEL_PATH)
    print(f"Trained on {len(dataset):,} rows; saved model to {MODEL_PATH}")
    print("Holdout metrics:")
    for name in ("accuracy", "precision", "recall", "f1_score"):
        print(f"  {name.replace('_', ' ').title()}: {metrics[name]:.3f}")
    print(f"  Confusion matrix [actual 0/1 x predicted 0/1]: {metrics['confusion_matrix']}")
    return artifact


if __name__ == "__main__":
    train_model()