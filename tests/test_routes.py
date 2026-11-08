"""
Integration tests for Flask application routes.
"""

import unittest
from app import app
from database import init_db, seed_sample_data

class TestFlaskRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        seed_sample_data()

    def setUp(self):
        self.client = app.test_client()
        app.config["TESTING"] = True

    def test_dashboard_route(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Electricity Consumption Analysis", response.data)
        self.assertIn(b"Dashboard", response.data)

    def test_consumers_route(self):
        response = self.client.get("/consumers")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Consumer Records", response.data)

    def test_meters_route(self):
        response = self.client.get("/meters")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Meter Hardware Records", response.data)

    def test_readings_route(self):
        response = self.client.get("/readings")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Meter Readings Log", response.data)

    def test_reports_route(self):
        response = self.client.get("/reports")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Consumption Reports", response.data)
        self.assertIn(b"High-Usage Anomaly Detection", response.data)
        self.assertIn(b"Reading Validation", response.data)

    def test_export_monthly_csv(self):
        response = self.client.get("/reports/export/monthly")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/csv")
        self.assertIn(b"Month,Consumer ID", response.data)

    def test_chart_trend(self):
        response = self.client.get("/chart/trend.png")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/png")

    def test_chart_consumer_comparison(self):
        response = self.client.get("/chart/consumer-comparison.png")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/png")

    def test_chart_regional(self):
        response = self.client.get("/chart/regional.png")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/png")

if __name__ == "__main__":
    unittest.main()
