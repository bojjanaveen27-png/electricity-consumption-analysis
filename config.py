"""
Configuration module for Electricity Consumption Analysis System.
Loads environment settings with sensible defaults for MySQL, with automatic
SQLite fallback support for seamless local development and testing.
"""

import os
from dotenv import load_dotenv

# Load variables from .env file if present
load_dotenv()

# Database Configuration
# Supported engines: 'mysql' (default) or 'sqlite'
DB_ENGINE = os.getenv("DB_ENGINE", "mysql").lower().strip()

# MySQL Connection Parameters
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "electricity_analysis")

# SQLite Database File (used when DB_ENGINE=sqlite or on automatic fallback)
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", os.path.join(os.path.dirname(__file__), "electricity_analysis.db"))

# Application & Analytical Parameters
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "electricity-analysis-secret-key-2026")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")

# Analytical threshold for flagging unusually high monthly usage (in kWh)
DEFAULT_HIGH_USAGE_THRESHOLD_KWH = float(os.getenv("HIGH_USAGE_THRESHOLD_KWH", "500.0"))
