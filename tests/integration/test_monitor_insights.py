"""Offline API contracts. Test doubles never enter the Mart or UI."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import psycopg2
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "monitoring" / "backend"))
from app.api.v1.endpoints.insights import router
from app.services import insights_service as service

app = FastAPI()
app.include_router(router, prefix="/api/v1/insights")
client = TestClient(app)


class InsightsTests(unittest.TestCase):
    def test_empty_contract(self):
        with patch.object(service, "query", return_value=[]):
            for path in ("salary-heatmap", "skill-combos", "clusters", "filters/options"):
                response = client.get("/api/v1/insights/" + path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.json(), {"status": "EMPTY", "reason": "NO_DATA", "data": None}
                )

    def test_unavailable_hides_credentials(self):
        with patch.object(service, "query", side_effect=psycopg2.OperationalError("secret")):
            response = client.get("/api/v1/insights/clusters")
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("secret", response.text)
            self.assertIn("MART_UNAVAILABLE", response.text)

    def test_invalid_thresholds(self):
        for args in ("min_support=2", "min_confidence=-1", "min_lift=-1", "limit=0"):
            self.assertEqual(client.get("/api/v1/insights/skill-combos?" + args).status_code, 422)

    def test_filters_are_bound_parameters(self):
        hostile = "' OR TRUE --"
        with patch.object(service, "query", return_value=[]) as query:
            service.salary(hostile, "Senior", "Backend")
            sql, params = query.call_args.args
            self.assertNotIn(hostile, sql)
            self.assertEqual(params, [hostile, "Senior", "Backend"])
            self.assertIn("1000000 AND 500000000", sql)

    def test_cluster_filter_uses_job_metadata_and_keeps_z_nullable(self):
        with patch.object(service, "query", return_value=[]) as query:
            service.clusters("Hà Nội", "Junior", "Data/AI")
            sql, params = query.call_args.args
            self.assertIn("LEFT JOIN curated_jobs", sql)
            self.assertNotIn("COALESCE(c.pca_z", sql)
            self.assertEqual(params, ["Hà Nội", "Junior", "Data/AI"])

    def test_macro_and_antecedent(self):
        with patch.object(service, "query", return_value=[]) as query:
            service.combos(0.02, 0.5, 1.2, "ALL", "Python", 20)
            self.assertEqual(
                query.call_args.args[1], (0.02, 0.5, 1.2, "ALL", "Python", "Python", 20)
            )


if __name__ == "__main__":
    unittest.main()
