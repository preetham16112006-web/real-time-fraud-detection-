"""API and decision-rule tests for the local demonstration application."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app, assess_probability
from database import database


class FraudDetectionApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.database_directory.name) / "test_transactions.db"
        self.database_path_patch = patch.object(database, "DB_PATH", self.database_path)
        self.database_path_patch.start()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        self.database_path_patch.stop()
        self.database_directory.cleanup()

    def test_decision_thresholds(self) -> None:
        self.assertEqual(assess_probability(0.299), ("LOW", "APPROVED", "SUCCESS"))
        self.assertEqual(assess_probability(0.30), ("MEDIUM", "REVIEW", "PENDING"))
        self.assertEqual(assess_probability(0.70), ("MEDIUM", "REVIEW", "PENDING"))
        self.assertEqual(assess_probability(0.701), ("HIGH", "BLOCKED", "DECLINED"))

    def test_prediction_is_scored_and_persisted(self) -> None:
        response = self.client.post(
            "/api/predict",
            json={
                "amount": 500,
                "transaction_time": "11:20",
                "device_id": "DEV-TEST-9001",
                "is_new_device": False,
                "location": "Tumkur",
                "transactions_last_5min": 1,
                "amount_last_5min": 250,
                "average_transaction_amount": 1200,
                "distance_from_usual_location": 4,
            },
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result["transaction_id"].startswith("TXN-"))
        self.assertGreaterEqual(result["fraud_probability"], 0)
        self.assertLessEqual(result["fraud_probability"], 1)
        self.assertEqual(result["risk_level"], assess_probability(result["fraud_probability"])[0])

        saved = self.client.get("/api/transactions").json()
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["transaction_id"], result["transaction_id"])
        self.assertEqual(saved[0]["device_id"], "DEV-TEST-9001")

    def test_validation_rejects_invalid_amount_and_time(self) -> None:
        invalid_payload = {
            "amount": 0,
            "transaction_time": "25:90",
            "device_id": "device",
            "is_new_device": False,
            "location": "Tumkur",
            "transactions_last_5min": 1,
            "amount_last_5min": 0,
            "average_transaction_amount": 1000,
            "distance_from_usual_location": 0,
        }
        response = self.client.post("/api/predict", json=invalid_payload)
        self.assertEqual(response.status_code, 422)

    def test_dashboard_stats_and_model_metrics(self) -> None:
        stats = self.client.get("/api/stats")
        metrics = self.client.get("/api/model-metrics")
        self.assertEqual(stats.status_code, 200)
        self.assertEqual(stats.json()["total_transactions"], 0)
        self.assertEqual(metrics.status_code, 200)
        self.assertIn("confusion_matrix", metrics.json())
        self.assertIn("f1_score", metrics.json())

    def test_clear_transaction_history_removes_rows_and_resets_stats(self) -> None:
        response = self.client.post(
            "/api/predict",
            json={
                "amount": 500,
                "transaction_time": "11:20",
                "device_id": "DEV-TEST-9001",
                "is_new_device": False,
                "location": "Tumkur",
                "transactions_last_5min": 1,
                "amount_last_5min": 250,
                "average_transaction_amount": 1200,
                "distance_from_usual_location": 4,
            },
        )
        self.assertEqual(response.status_code, 200)
        cleared = self.client.delete("/api/transactions")
        self.assertEqual(cleared.status_code, 200)
        self.assertEqual(cleared.json()["deleted_count"], 1)
        self.assertEqual(self.client.get("/api/transactions").json(), [])
        self.assertEqual(self.client.get("/api/stats").json()["total_transactions"], 0)

    def test_dashboard_and_static_assets_load(self) -> None:
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertIn("REAL-TIME FRAUD DETECTION SYSTEM", self.client.get("/").text.upper())
        self.assertEqual(self.client.get("/static/script.js").status_code, 200)
        self.assertEqual(self.client.get("/static/style.css").status_code, 200)


if __name__ == "__main__":
    unittest.main() 