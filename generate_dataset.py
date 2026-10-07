"""Generate a reproducible synthetic transaction dataset for classroom use."""

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "transactions.csv"
ROW_COUNT = 12_000
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


def generate_dataset(row_count: int = ROW_COUNT, seed: int = 42) -> pd.DataFrame:
    """Create varied transactions and probabilistic labels with interaction effects."""
    rng = np.random.default_rng(seed)
    average_amount = np.clip(rng.lognormal(np.log(1_800), 0.75, row_count), 150, 20_000)
    amount = np.clip(
        average_amount * rng.lognormal(0, 0.9, row_count), 50, 150_000
    )
    hour = rng.integers(0, 24, row_count)
    is_new_device = rng.binomial(1, 0.19, row_count)
    distance = np.clip(rng.gamma(1.45, 48, row_count), 0, 1_200)
    location_change = (distance >= 100).astype(int)
    transactions_last_5min = np.clip(rng.poisson(1.4, row_count), 0, 12)
    amount_last_5min = np.where(
        transactions_last_5min == 0,
        0,
        np.clip(
            average_amount
            * transactions_last_5min
            * rng.lognormal(-0.15, 0.8, row_count),
            0,
            100_000,
        ),
    )

    late_night = ((hour <= 4) | (hour >= 23)).astype(float)
    high_amount = np.clip(np.log1p(amount / average_amount) / 3.2, 0, 1.5)
    high_recent_spend = np.clip(
        np.log1p(amount_last_5min / np.maximum(average_amount, 1)) / 3.2, 0, 1.5
    )
    high_velocity = np.clip(transactions_last_5min / 7, 0, 1.5)
    far_from_usual = np.clip(np.log1p(distance) / np.log1p(1_200), 0, 1.5)

    # Labels depend on combinations and noise; no single signal guarantees fraud.
    log_odds = (
        -4.0
        + 1.45 * high_amount
        + 0.72 * late_night
        + 0.9 * is_new_device
        + 0.92 * location_change
        + 0.72 * high_velocity
        + 0.82 * high_recent_spend
        + 0.9 * far_from_usual
        + 1.25 * high_amount * is_new_device
        + 0.9 * late_night * location_change
        + 0.8 * high_velocity * high_recent_spend
        + rng.normal(0, 0.65, row_count)
    )
    fraud_probability = 1 / (1 + np.exp(-log_odds))
    fraud = rng.binomial(1, fraud_probability)

    return pd.DataFrame(
        {
            "amount": np.round(amount, 2),
            "hour": hour,
            "is_new_device": is_new_device,
            "location_change": location_change,
            "transactions_last_5min": transactions_last_5min,
            "amount_last_5min": np.round(amount_last_5min, 2),
            "average_transaction_amount": np.round(average_amount, 2),
            "distance_from_usual_location": np.round(distance, 2),
            "fraud": fraud,
        }
    )


def main() -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    dataset = generate_dataset()
    dataset.to_csv(DATA_PATH, index=False)
    print(f"Generated {len(dataset):,} transactions at {DATA_PATH}")
    print(f"Synthetic fraud rate: {dataset['fraud'].mean():.1%}")


if __name__ == "__main__":
    main()