"""SQLite persistence helpers for transaction monitoring."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "database" / "transactions.db"


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id TEXT NOT NULL UNIQUE,
                amount REAL NOT NULL,
                transaction_time TEXT NOT NULL,
                device_id TEXT NOT NULL,
                is_new_device INTEGER NOT NULL,
                location TEXT NOT NULL,
                transactions_last_5min INTEGER NOT NULL,
                amount_last_5min REAL NOT NULL,
                average_transaction_amount REAL NOT NULL,
                distance_from_usual_location REAL NOT NULL,
                fraud_probability REAL NOT NULL,
                risk_level TEXT NOT NULL,
                decision TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def save_transaction(transaction: dict[str, Any]) -> None:
    columns = (
        "transaction_id",
        "amount",
        "transaction_time",
        "device_id",
        "is_new_device",
        "location",
        "transactions_last_5min",
        "amount_last_5min",
        "average_transaction_amount",
        "distance_from_usual_location",
        "fraud_probability",
        "risk_level",
        "decision",
        "status",
        "created_at",
    )
    placeholders = ", ".join("?" for _ in columns)
    with get_connection() as connection:
        connection.execute(
            f"INSERT INTO transactions ({', '.join(columns)}) VALUES ({placeholders})",
            tuple(transaction[column] for column in columns),
        )


def get_recent_transactions(limit: int = 50) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM transactions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def clear_transactions() -> int:
    with get_connection() as connection:
        cursor = connection.execute("DELETE FROM transactions")
        return cursor.rowcount


def get_dashboard_stats() -> dict[str, int | float]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN decision = 'APPROVED' THEN 1 ELSE 0 END) AS approved,
                   SUM(CASE WHEN decision = 'REVIEW' THEN 1 ELSE 0 END) AS review,
                   SUM(CASE WHEN decision = 'BLOCKED' THEN 1 ELSE 0 END) AS blocked,
                   AVG(fraud_probability) AS average_probability
            FROM transactions
            """
        ).fetchone()
    total = int(row["total"] or 0)
    average_probability = row["average_probability"]
    return {
        "total_transactions": total,
        "approved": int(row["approved"] or 0),
        "under_review": int(row["review"] or 0),
        "blocked": int(row["blocked"] or 0),
        "fraud_percentage": round(float(average_probability or 0) * 100, 2),
    }