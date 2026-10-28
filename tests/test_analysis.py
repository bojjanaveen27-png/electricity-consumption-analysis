"""
Unit tests for the analytical engine (analysis.py) and data processing rules.
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime

import analysis

class TestElectricityAnalysis(unittest.TestCase):

    def setUp(self):
        """
        Creates synthetic reading DataFrame for testing various calculation edge cases.
        """
        data = [
            # Meter 1: Normal consecutive readings
            {"reading_id": 1, "meter_id": 1, "meter_code": "M-101", "consumer_id": 1, "consumer_type": "Residential", "region": "Nellore", "reading_date": "2026-01-01", "cumulative_kwh": 1000.0},
            {"reading_id": 2, "meter_id": 1, "meter_code": "M-101", "consumer_id": 1, "consumer_type": "Residential", "region": "Nellore", "reading_date": "2026-02-01", "cumulative_kwh": 1250.0},
            {"reading_id": 3, "meter_id": 1, "meter_code": "M-101", "consumer_id": 1, "consumer_type": "Residential", "region": "Nellore", "reading_date": "2026-03-01", "cumulative_kwh": 1600.0},

            # Meter 2: First reading + High usage
            {"reading_id": 4, "meter_id": 2, "meter_code": "M-102", "consumer_id": 2, "consumer_type": "Commercial", "region": "Vijayawada", "reading_date": "2026-01-01", "cumulative_kwh": 5000.0},
            {"reading_id": 5, "meter_id": 2, "meter_code": "M-102", "consumer_id": 2, "consumer_type": "Commercial", "region": "Vijayawada", "reading_date": "2026-02-01", "cumulative_kwh": 5800.0},

            # Meter 3: Rollover / Reset scenario
            {"reading_id": 6, "meter_id": 3, "meter_code": "M-103", "consumer_id": 3, "consumer_type": "Industrial", "region": "Tirupati", "reading_date": "2026-01-01", "cumulative_kwh": 9900.0},
            {"reading_id": 7, "meter_id": 3, "meter_code": "M-103", "consumer_id": 3, "consumer_type": "Industrial", "region": "Tirupati", "reading_date": "2026-02-01", "cumulative_kwh": 9980.0},
            {"reading_id": 8, "meter_id": 3, "meter_code": "M-103", "consumer_id": 3, "consumer_type": "Industrial", "region": "Tirupati", "reading_date": "2026-03-01", "cumulative_kwh": 150.0}, # Rollover

            # Meter 4: Invalid date order
            {"reading_id": 9, "meter_id": 4, "meter_code": "M-104", "consumer_id": 4, "consumer_type": "Residential", "region": "Nellore", "reading_date": "2026-02-01", "cumulative_kwh": 500.0},
            {"reading_id": 10, "meter_id": 4, "meter_code": "M-104", "consumer_id": 4, "consumer_type": "Residential", "region": "Nellore", "reading_date": "2026-01-15", "cumulative_kwh": 600.0}  # Earlier date
        ]

        df = pd.DataFrame(data)
        df["reading_date"] = pd.to_datetime(df["reading_date"])
        df["cumulative_kwh"] = pd.to_numeric(df["cumulative_kwh"])

        # Execute core analytical pipeline
        df["previous_kwh"] = df.groupby("meter_id")["cumulative_kwh"].shift(1)
        df["previous_date"] = df.groupby("meter_id")["reading_date"].shift(1)
        df["consumption_kwh"] = df["cumulative_kwh"] - df["previous_kwh"]
        df["days_between"] = (df["reading_date"] - df["previous_date"]).dt.days

        conditions = [
            df["previous_kwh"].isna(),
            df["days_between"] <= 0,
            df["consumption_kwh"] < 0
        ]
        choices = [
            "FIRST READING",
            "INVALID DATE ORDER",
            "RESET/ROLLOVER REVIEW"
        ]
        df["status"] = np.select(conditions, choices, default="VALID")
        df["analytical_kwh"] = np.where(df["status"] == "VALID", df["consumption_kwh"], np.nan)
        df["daily_avg_kwh"] = np.where(
            (df["status"] == "VALID") & (df["days_between"] > 0),
            df["consumption_kwh"] / df["days_between"],
            np.nan
        )

        self.df = df

    def test_first_reading_status(self):
        """Verify initial reading for any meter is classified as FIRST READING and excluded from consumption."""
        first_readings = self.df[self.df["status"] == "FIRST READING"]
        self.assertEqual(len(first_readings), 4) # One for each of the 4 meters
        for _, row in first_readings.iterrows():
            self.assertTrue(pd.isna(row["analytical_kwh"]))

    def test_valid_consumption_calculation(self):
        """Verify normal consecutive consumption equals current - previous cumulative kWh."""
        m1_feb = self.df[(self.df["meter_id"] == 1) & (self.df["reading_id"] == 2)].iloc[0]
        self.assertEqual(m1_feb["status"], "VALID")
        self.assertEqual(m1_feb["analytical_kwh"], 250.0)
        self.assertEqual(m1_feb["days_between"], 31)

        m1_mar = self.df[(self.df["meter_id"] == 1) & (self.df["reading_id"] == 3)].iloc[0]
        self.assertEqual(m1_mar["status"], "VALID")
        self.assertEqual(m1_mar["analytical_kwh"], 350.0)

    def test_meter_rollover_flagging(self):
        """Verify that a drop in cumulative reading is flagged as RESET/ROLLOVER REVIEW and not counted as negative."""
        rollover_row = self.df[self.df["reading_id"] == 8].iloc[0]
        self.assertEqual(rollover_row["status"], "RESET/ROLLOVER REVIEW")
        self.assertTrue(pd.isna(rollover_row["analytical_kwh"]))
        self.assertLess(rollover_row["consumption_kwh"], 0)

    def test_invalid_date_order(self):
        """Verify non-chronological readings are flagged as INVALID DATE ORDER."""
        invalid_row = self.df[self.df["reading_id"] == 10].iloc[0]
        self.assertEqual(invalid_row["status"], "INVALID DATE ORDER")
        self.assertTrue(pd.isna(invalid_row["analytical_kwh"]))

    def test_monthly_summary(self):
        """Verify monthly aggregation using Pandas period grouping."""
        monthly = analysis.get_monthly_consumption_summary(self.df)
        self.assertFalse(monthly.empty)
        # Check that month strings are YYYY-MM
        self.assertTrue(all(len(m) == 7 and m[4] == '-' for m in monthly["month"]))

    def test_high_usage_detection(self):
        """Verify configurable threshold filters high consumption records accurately."""
        monthly = analysis.get_monthly_consumption_summary(self.df)
        high = analysis.get_high_usage_analysis(monthly, threshold_kwh=500.0)
        # Consumer 2 used 800 kWh in Feb 2026, which exceeds 500 kWh threshold
        self.assertGreaterEqual(len(high), 1)
        self.assertTrue(all(val >= 500.0 for val in high["consumption_kwh"]))

    def test_validation_report_generation(self):
        """Verify validation report contains all non-valid records and diagnostic notes."""
        val_report = analysis.get_validation_report(self.df)
        self.assertGreater(len(val_report), 0)
        self.assertIn("audit_note", val_report.columns)

if __name__ == "__main__":
    unittest.main()
