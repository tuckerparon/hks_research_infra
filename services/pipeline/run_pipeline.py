# ── HUMAN REVIEW ──────────────────────────────────────────
# Reviewer: Tucker Paron
# Date: 2026-05-05
# Changes from AI draft: 
#   - Added docstrings to functions
#   - AnomalyDetector uses numpy and psycopg2 only knows how to serialize Python's built-in types. I added int() and float() enforcement to allow psycopg2 to be compatible
# Notes:
#   - In prod run_cycle would pull from S3 or a real data source, not csvs
#   - Questioned the purpose of the logger, but this is what creates output for debugging from "docker compose logs pipeline -f"
# ──────────────────────────────────────────────────────────

import os
import time
import logging
import psycopg2
from psycopg2.extras import execute_values

from generate_data import DataGenerator
from anomaly_detector import AnomalyDetector

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'db'),
    'port': int(os.getenv('POSTGRES_PORT', 5432)),
    'dbname': os.getenv('POSTGRES_DB'),
    'user': os.getenv('POSTGRES_USER'),
    'password': os.getenv('POSTGRES_PASSWORD'),
}

INTERVAL_MINUTES = int(os.getenv('PIPELINE_INTERVAL_MINUTES', 5))


def wait_for_db():
    """Block until PostgreSQL accepts connections, retrying every 2 seconds.

    Necessary because Docker starts all containers in parallel; the pipeline
    container is typically ready before the database has finished initializing.
    The healthcheck in docker-compose.yml handles this too, but this provides
    an extra safety net for cases where the pipeline restarts independently.
    """
    while True:
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            conn.close()
            logger.info("Database ready")
            return
        except psycopg2.OperationalError:
            logger.info("Waiting for database...")
            time.sleep(2)


def run_cycle(conn, detector, batch_size):
    """Run one full pipeline cycle: generate → ingest → detect anomalies → store.

    Args:
        conn: Open psycopg2 connection (reused across cycles to avoid reconnect overhead).
        detector: AnomalyDetector instance (stateless; reused for the same reason).
        batch_size: Number of sensor readings to generate and ingest this cycle.

    The CSV-level id from DataGenerator is intentionally dropped — the DB generates
    its own SERIAL id via RETURNING so anomaly foreign keys reference real DB rows.
    AnomalyDetector returns numpy int64/float64 types; these are cast to Python
    int/float before insertion because psycopg2 cannot serialize numpy scalars.
    """
    logger.info(f"Generating {batch_size} sensor readings...")
    generator = DataGenerator(anomaly_rate=0.03)
    readings = generator.generate_dataset(batch_size)

    # Build rows for bulk insert, skipping the CSV id — DB generates its own
    rows = [
        (r['timestamp'], r['sensor_id'], r['temperature'],
         r['humidity'], r['pressure'], r['location'])
        for r in readings
    ]

    with conn.cursor() as cur:
        # Insert and get back DB-generated ids so anomalies can reference them
        db_rows = execute_values(
            cur,
            """
            INSERT INTO sensor_readings
                (timestamp, sensor_id, temperature, humidity, pressure, location)
            VALUES %s
            RETURNING id, timestamp, sensor_id, temperature, humidity, pressure, location
            """,
            rows,
            fetch=True
        )
    conn.commit()

    # Convert returned rows to dicts AnomalyDetector expects
    db_readings = [
        {
            'id': row[0],
            'timestamp': row[1].isoformat() if hasattr(row[1], 'isoformat') else row[1],
            'sensor_id': row[2],
            'temperature': row[3],
            'humidity': row[4],
            'pressure': row[5],
            'location': row[6],
        }
        for row in db_rows
    ]

    anomalies = detector.detect_anomalies(db_readings)

    if anomalies:
        anomaly_rows = [
            (int(a['sensor_data_id']), a['anomaly_type'],
             float(a['confidence_score']), a['detected_at'])
            for a in anomalies
        ]
        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO anomalies
                    (sensor_data_id, anomaly_type, confidence_score, detected_at)
                VALUES %s
                """,
                anomaly_rows
            )
        conn.commit()

    logger.info(
        f"Cycle complete — {len(db_readings)} readings, {len(anomalies)} anomalies detected"
    )


def main():
    """Entry point. Seeds the DB with a large initial batch, then runs on a fixed interval.

    The first cycle uses batch_size=10,000 to give the API and dashboard meaningful
    data immediately. Subsequent cycles use batch_size=1,000 to simulate ongoing
    sensor ingestion. The interval is configured via PIPELINE_INTERVAL_MINUTES (default 5).
    """
    wait_for_db()
    detector = AnomalyDetector()
    conn = psycopg2.connect(**DB_CONFIG)

    # First cycle seeds the DB with a larger batch
    run_cycle(conn, detector, batch_size=10000)

    while True:
        logger.info(f"Sleeping {INTERVAL_MINUTES} minutes until next cycle...")
        time.sleep(INTERVAL_MINUTES * 60)
        run_cycle(conn, detector, batch_size=1000)


if __name__ == '__main__':
    main()
