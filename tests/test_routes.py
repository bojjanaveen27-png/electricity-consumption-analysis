"""
Integration tests for Flask application routes and Authentication security gate.
"""

import unittest
from app import app
from database import init_db, seed_sample_data
import config

class TestFlaskRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        seed_sample_data()

    def setUp(self):
        self.client = app.test_client()
        app.config["TESTING"] = True

    def login_client(self):
        """Helper to establish an authenticated session for protected route tests."""
        with self.client.session_transaction() as sess:
            sess["logged_in"] = True
            sess["username"] = config.ADMIN_USERNAME

    # --- Authentication & Access Control Tests ---

    def test_unauthenticated_access_redirects_to_login(self):
        """Verify unauthenticated user cannot view dashboard or reports and is redirected."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

        response = self.client.get("/reports")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_login_page_renders(self):
        """Verify login portal page renders successfully."""
        response = self.client.get("/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Protected Access", response.data)
        self.assertIn(b"Sign In to Dashboard", response.data)

    def test_login_failure_invalid_credentials(self):
        """Verify incorrect password results in access denied."""
        response = self.client.post("/login", data={
            "username": config.ADMIN_USERNAME,
            "password": "WrongPassword123"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Access denied", response.data)

    def test_login_success(self):
        """Verify valid admin credentials grant access to dashboard."""
        response = self.client.post("/login", data={
            "username": config.ADMIN_USERNAME,
            "password": config.ADMIN_PASSWORD
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Dashboard", response.data)
        self.assertIn(b"Welcome", response.data)

    def test_logout(self):
        """Verify logout clears session and redirects to login."""
        self.login_client()
        response = self.client.get("/logout", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"signed out successfully", response.data)

    # --- Authenticated Application Route Tests ---

    def test_dashboard_route_authenticated(self):
        self.login_client()
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Electricity Consumption Analysis", response.data)
        self.assertIn(b"Dashboard", response.data)

    def test_consumers_route_authenticated(self):
        self.login_client()
        response = self.client.get("/consumers")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Consumer Records", response.data)

    def test_meters_route_authenticated(self):
        self.login_client()
        response = self.client.get("/meters")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Meter Hardware Records", response.data)

    def test_readings_route_authenticated(self):
        self.login_client()
        response = self.client.get("/readings")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Meter Readings Log", response.data)

    def test_reports_route_authenticated(self):
        self.login_client()
        response = self.client.get("/reports")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Consumption Reports", response.data)
        self.assertIn(b"High-Usage Anomaly Detection", response.data)
        self.assertIn(b"Reading Validation", response.data)

    def test_export_monthly_csv_authenticated(self):
        self.login_client()
        response = self.client.get("/reports/export/monthly")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/csv")
        self.assertIn(b"Month,Consumer ID", response.data)

    def test_chart_trend_authenticated(self):
        self.login_client()
        response = self.client.get("/chart/trend.png")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/png")

    def test_chart_consumer_comparison_authenticated(self):
        self.login_client()
        response = self.client.get("/chart/consumer-comparison.png")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/png")

    def test_chart_regional_authenticated(self):
        self.login_client()
        response = self.client.get("/chart/regional.png")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/png")

if __name__ == "__main__":
    unittest.main()
