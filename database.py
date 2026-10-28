"""
Database connection and query abstraction module.
Supports MySQL as the primary production database as requested,
with seamless automatic SQLite fallback for zero-configuration local runs and testing.
"""

import os
import sqlite3
import re
import logging
from datetime import date
import config

logger = logging.getLogger(__name__)

# Track active database backend
_ACTIVE_ENGINE = None

def get_active_engine():
    global _ACTIVE_ENGINE
    if _ACTIVE_ENGINE is None:
        _detect_active_engine()
    return _ACTIVE_ENGINE

def _detect_active_engine():
    global _ACTIVE_ENGINE
    if config.DB_ENGINE == "sqlite":
        _ACTIVE_ENGINE = "sqlite"
        return

    # Try connecting to MySQL
    try:
        import mysql.connector
        conn = mysql.connector.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME,
            connect_timeout=3
        )
        conn.close()
        _ACTIVE_ENGINE = "mysql"
        print(f"[DB] Connected to MySQL database '{config.DB_NAME}' at {config.DB_HOST}:{config.DB_PORT}.")
    except Exception as e:
        print(f"[DB Warning] Could not connect to MySQL ({e}).")
        print("[DB] Falling back to local SQLite database for uninterrupted operation.")
        _ACTIVE_ENGINE = "sqlite"

def get_connection():
    """
    Returns an open database connection based on the active engine.
    """
    engine = get_active_engine()
    if engine == "mysql":
        import mysql.connector
        return mysql.connector.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME
        )
    else:
        # SQLite connection
        conn = sqlite3.connect(config.SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        # Enable foreign key support in SQLite
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

def execute_query(sql, params=(), fetch=True):
    """
    Executes a SQL query with standard parameterized arguments (%s syntax).
    Automatically adapts query placeholders if running on SQLite.
    Returns list of dicts for SELECT, or None / rowcount for INSERT/UPDATE/DELETE.
    """
    engine = get_active_engine()
    conn = get_connection()
    try:
        if engine == "mysql":
            cur = conn.cursor(dictionary=True)
            cur.execute(sql, params)
            result = cur.fetchall() if fetch else cur.lastrowid
            if not fetch:
                conn.commit()
            cur.close()
            return result
        else:
            # SQLite: Convert %s to ?
            # Be careful not to replace %% or quoted strings
            sqlite_sql = sql.replace("%s", "?")
            cur = conn.cursor()
            cur.execute(sqlite_sql, params)
            if fetch:
                rows = cur.fetchall()
                result = [dict(row) for row in rows]
            else:
                conn.commit()
                result = cur.lastrowid
            cur.close()
            return result
    finally:
        conn.close()

def init_db():
    """
    Initializes tables if they do not exist.
    """
    engine = get_active_engine()
    if engine == "mysql":
        # Run schema via query if database exists
        # Tables will be created using standard schema definitions
        queries = [
            """
            CREATE TABLE IF NOT EXISTS consumers (
                consumer_id INT AUTO_INCREMENT PRIMARY KEY,
                consumer_type VARCHAR(40) NOT NULL,
                region VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB;
            """,
            """
            CREATE TABLE IF NOT EXISTS meters (
                meter_id INT AUTO_INCREMENT PRIMARY KEY,
                consumer_id INT NOT NULL,
                meter_code VARCHAR(50) NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_meter_consumer FOREIGN KEY (consumer_id)
                  REFERENCES consumers(consumer_id) ON UPDATE CASCADE ON DELETE RESTRICT
            ) ENGINE=InnoDB;
            """,
            """
            CREATE TABLE IF NOT EXISTS meter_readings (
                reading_id BIGINT AUTO_INCREMENT PRIMARY KEY,
                meter_id INT NOT NULL,
                reading_date DATE NOT NULL,
                cumulative_kwh DECIMAL(12,3) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_reading_meter FOREIGN KEY (meter_id)
                  REFERENCES meters(meter_id) ON UPDATE CASCADE ON DELETE RESTRICT,
                CONSTRAINT uq_meter_date UNIQUE (meter_id, reading_date),
                CONSTRAINT chk_cumulative_kwh CHECK (cumulative_kwh >= 0),
                INDEX idx_meter_date (meter_id, reading_date)
            ) ENGINE=InnoDB;
            """
        ]
        conn = get_connection()
        try:
            cur = conn.cursor()
            for q in queries:
                cur.execute(q)
            conn.commit()
            cur.close()
        finally:
            conn.close()
    else:
        # SQLite Schema
        queries = [
            """
            CREATE TABLE IF NOT EXISTS consumers (
                consumer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                consumer_type TEXT NOT NULL,
                region TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS meters (
                meter_id INTEGER PRIMARY KEY AUTOINCREMENT,
                consumer_id INTEGER NOT NULL,
                meter_code TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (consumer_id) REFERENCES consumers(consumer_id) ON UPDATE CASCADE ON DELETE RESTRICT
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS meter_readings (
                reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
                meter_id INTEGER NOT NULL,
                reading_date TEXT NOT NULL,
                cumulative_kwh REAL NOT NULL CHECK(cumulative_kwh >= 0),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(meter_id, reading_date),
                FOREIGN KEY (meter_id) REFERENCES meters(meter_id) ON UPDATE CASCADE ON DELETE RESTRICT
            );
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_meter_date ON meter_readings(meter_id, reading_date);
            """
        ]
        conn = get_connection()
        try:
            cur = conn.cursor()
            for q in queries:
                cur.execute(q)
            conn.commit()
            cur.close()
        finally:
            conn.close()

def seed_sample_data():
    """
    Seeds comprehensive realistic records across multiple consumers, regions, and months.
    Includes normal consumption, high-usage consumption, and one flagged rollover for demonstration.
    """
    init_db()
    existing_consumers = execute_query("SELECT COUNT(*) AS count FROM consumers")
    count = existing_consumers[0]["count"] if existing_consumers else 0
    if count > 0:
        return False  # Already seeded

    # 1. Insert Consumers
    consumers_data = [
        ("Residential", "Nellore"),
        ("Commercial", "Vijayawada"),
        ("Residential", "Tirupati"),
        ("Industrial", "Visakhapatnam"),
        ("Commercial", "Guntur")
    ]
    for c_type, reg in consumers_data:
        execute_query("INSERT INTO consumers (consumer_type, region) VALUES (%s, %s)", (c_type, reg), fetch=False)

    # 2. Insert Meters
    meters_data = [
        (1, "MTR-1001"), # Residential - Nellore
        (2, "MTR-1002"), # Commercial - Vijayawada (High usage)
        (3, "MTR-1003"), # Residential - Tirupati
        (4, "MTR-1004"), # Industrial - Visakhapatnam (Very high usage)
        (5, "MTR-1005")  # Commercial - Guntur (Will demonstrate rollover)
    ]
    for cid, mcode in meters_data:
        execute_query("INSERT INTO meters (consumer_id, meter_code) VALUES (%s, %s)", (cid, mcode), fetch=False)

    # 3. Insert Dated Meter Readings (Cumulative kWh)
    # Consecutive monthly readings for 2026
    readings = [
        # Meter 1: Normal residential (average 200 - 350 kWh/month)
        (1, "2026-01-01", 1200.0),
        (1, "2026-02-01", 1450.0), # 250 kWh
        (1, "2026-03-01", 1725.0), # 275 kWh
        (1, "2026-04-01", 2040.0), # 315 kWh
        (1, "2026-05-01", 2390.0), # 350 kWh
        (1, "2026-06-01", 2760.0), # 370 kWh

        # Meter 2: Commercial (500 - 800 kWh/month, triggers high usage threshold)
        (2, "2026-01-01", 5000.0),
        (2, "2026-02-01", 5620.0), # 620 kWh -> HIGH USAGE
        (2, "2026-03-01", 6270.0), # 650 kWh -> HIGH USAGE
        (2, "2026-04-01", 6950.0), # 680 kWh -> HIGH USAGE
        (2, "2026-05-01", 7680.0), # 730 kWh -> HIGH USAGE
        (2, "2026-06-01", 8450.0), # 770 kWh -> HIGH USAGE

        # Meter 3: Residential moderate
        (3, "2026-01-01", 800.0),
        (3, "2026-02-01", 940.0),  # 140 kWh
        (3, "2026-03-01", 1100.0), # 160 kWh
        (3, "2026-04-01", 1270.0), # 170 kWh
        (3, "2026-05-01", 1460.0), # 190 kWh
        (3, "2026-06-01", 1680.0), # 220 kWh

        # Meter 4: Industrial (High continuous load)
        (4, "2026-01-01", 15000.0),
        (4, "2026-02-01", 16850.0), # 1850 kWh -> HIGH USAGE
        (4, "2026-03-01", 18800.0), # 1950 kWh -> HIGH USAGE
        (4, "2026-04-01", 20900.0), # 2100 kWh -> HIGH USAGE
        (4, "2026-05-01", 23150.0), # 2250 kWh -> HIGH USAGE
        (4, "2026-06-01", 25500.0), # 2350 kWh -> HIGH USAGE

        # Meter 5: Demonstrates meter replacement / rollover scenario
        (5, "2026-01-01", 9850.0),
        (5, "2026-02-01", 9980.0), # 130 kWh
        (5, "2026-03-01", 120.0),  # Lower reading -> Triggers RESET/ROLLOVER REVIEW
        (5, "2026-04-01", 450.0)   # 330 kWh
    ]

    for mid, rdate, kwh in readings:
        execute_query(
            "INSERT INTO meter_readings (meter_id, reading_date, cumulative_kwh) VALUES (%s, %s, %s)",
            (mid, rdate, kwh),
            fetch=False
        )

    return True
