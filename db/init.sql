-- ── HUMAN REVIEW ──────────────────────────────────────────
-- Reviewer: Tucker Paron
-- Date: 2026-05-05
-- Changes from AI draft: None
-- Notes: I signed off on this exact code in INFRASTRUCTURE_PLAN.md.
-- ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sensor_readings (
    id          SERIAL PRIMARY KEY,
    timestamp   TIMESTAMPTZ NOT NULL,
    sensor_id   VARCHAR(50) NOT NULL,
    temperature FLOAT,
    humidity    FLOAT,
    pressure    FLOAT,
    location    VARCHAR(100),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sensor_readings_sensor_id ON sensor_readings(sensor_id);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_timestamp ON sensor_readings(timestamp);

CREATE TABLE IF NOT EXISTS anomalies (
    id               SERIAL PRIMARY KEY,
    sensor_data_id   INTEGER REFERENCES sensor_readings(id),
    anomaly_type     VARCHAR(100) NOT NULL,
    confidence_score FLOAT NOT NULL,
    detected_at      TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_anomalies_sensor_data_id ON anomalies(sensor_data_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_detected_at ON anomalies(detected_at);
