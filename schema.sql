-- ====================================================================
-- Electricity Consumption Analysis System - MySQL Database Schema
-- Entities: consumers, meters, meter_readings
-- ====================================================================

CREATE DATABASE IF NOT EXISTS electricity_analysis
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE electricity_analysis;

-- 1. Consumers Entity
CREATE TABLE IF NOT EXISTS consumers (
    consumer_id INT AUTO_INCREMENT PRIMARY KEY,
    consumer_type VARCHAR(40) NOT NULL COMMENT 'Residential, Commercial, Industrial, Agricultural',
    region VARCHAR(100) NOT NULL COMMENT 'Geographic zone, city, or district',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 2. Meters Entity
CREATE TABLE IF NOT EXISTS meters (
    meter_id INT AUTO_INCREMENT PRIMARY KEY,
    consumer_id INT NOT NULL,
    meter_code VARCHAR(50) NOT NULL UNIQUE COMMENT 'Unique physical meter serial identifier',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_meter_consumer FOREIGN KEY (consumer_id)
      REFERENCES consumers(consumer_id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- 3. Meter Readings Entity
CREATE TABLE IF NOT EXISTS meter_readings (
    reading_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    meter_id INT NOT NULL,
    reading_date DATE NOT NULL COMMENT 'Date when cumulative reading was taken',
    cumulative_kwh DECIMAL(12,3) NOT NULL COMMENT 'Raw meter counter in Kilowatt-hours (kWh)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_reading_meter FOREIGN KEY (meter_id)
      REFERENCES meters(meter_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT uq_meter_date UNIQUE (meter_id, reading_date),
    CONSTRAINT chk_cumulative_kwh CHECK (cumulative_kwh >= 0),
    INDEX idx_meter_date (meter_id, reading_date)
) ENGINE=InnoDB;

-- 4. Users / Authentication Entity
CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;


-- ====================================================================
-- Sample Seed Data for Demonstration & Testing
-- ====================================================================

INSERT INTO consumers (consumer_type, region) VALUES
('Residential', 'Nellore'),
('Commercial', 'Vijayawada'),
('Residential', 'Tirupati'),
('Industrial', 'Visakhapatnam'),
('Commercial', 'Guntur')
ON DUPLICATE KEY UPDATE region=VALUES(region);

INSERT INTO meters (consumer_id, meter_code) VALUES
(1, 'MTR-1001'),
(2, 'MTR-1002'),
(3, 'MTR-1003'),
(4, 'MTR-1004'),
(5, 'MTR-1005')
ON DUPLICATE KEY UPDATE meter_code=VALUES(meter_code);

-- Reading History (Consecutive Monthly Readings)
INSERT INTO meter_readings (meter_id, reading_date, cumulative_kwh) VALUES
-- Meter 1: Residential Nellore
(1, '2026-01-01', 1200.000),
(1, '2026-02-01', 1450.000),
(1, '2026-03-01', 1725.000),
(1, '2026-04-01', 2040.000),
(1, '2026-05-01', 2390.000),
(1, '2026-06-01', 2760.000),

-- Meter 2: Commercial Vijayawada (Exceeds 500 kWh threshold)
(2, '2026-01-01', 5000.000),
(2, '2026-02-01', 5620.000),
(2, '2026-03-01', 6270.000),
(2, '2026-04-01', 6950.000),
(2, '2026-05-01', 7680.000),
(2, '2026-06-01', 8450.000),

-- Meter 3: Residential Tirupati
(3, '2026-01-01', 800.000),
(3, '2026-02-01', 940.000),
(3, '2026-03-01', 1100.000),
(3, '2026-04-01', 1270.000),
(3, '2026-05-01', 1460.000),
(3, '2026-06-01', 1680.000),

-- Meter 4: Industrial Visakhapatnam (High continuous load)
(4, '2026-01-01', 15000.000),
(4, '2026-02-01', 16850.000),
(4, '2026-03-01', 18800.000),
(4, '2026-04-01', 20900.000),
(4, '2026-05-01', 23150.000),
(4, '2026-06-01', 25500.000),

-- Meter 5: Commercial Guntur (Contains rollover for audit verification)
(5, '2026-01-01', 9850.000),
(5, '2026-02-01', 9980.000),
(5, '2026-03-01', 120.000),
(5, '2026-04-01', 450.000)
ON DUPLICATE KEY UPDATE cumulative_kwh=VALUES(cumulative_kwh);
