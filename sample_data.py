"""
Utility script to seed or reset sample records for demonstration and testing.
Can be executed directly: `python sample_data.py`
"""

import sys
from database import init_db, seed_sample_data, execute_query, get_active_engine

def run_seed():
    print("=" * 60)
    print("Electricity Consumption Analysis System - Sample Data Seeder")
    print("=" * 60)
    print(f"Active database backend: {get_active_engine().upper()}")

    init_db()
    result = seed_sample_data()
    if result:
        print("[SUCCESS] Sample consumers, meters, and monthly readings loaded.")
    else:
        print("[INFO] Records already exist in the database. No duplicate data added.")

    consumers = execute_query("SELECT COUNT(*) AS count FROM consumers")[0]["count"]
    meters = execute_query("SELECT COUNT(*) AS count FROM meters")[0]["count"]
    readings = execute_query("SELECT COUNT(*) AS count FROM meter_readings")[0]["count"]

    print(f"Summary: {consumers} Consumers, {meters} Meters, {readings} Readings.")
    print("=" * 60)

if __name__ == "__main__":
    run_seed()
