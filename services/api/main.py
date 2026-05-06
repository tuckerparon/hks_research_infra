# ── HUMAN REVIEW ──────────────────────────────────────────
# Reviewer: Tucker Paron
# Date: 2026-05-05
# Changes from AI draft:
#   - Removed /api/readings and /api/stats — not required by README
#   - Removed get_reading (single-resource lookup) — not required by README
# Notes:
#   - For sensor readings API call, I disputed the fallback to "all sensors" when requesting
#     a sensor_id that doesn't exist. This is the correct fallback given sensor_id is not a required input.
# ──────────────────────────────────────────────────────────

from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Query

from database import get_conn
from models import Anomaly
from utils import z_to_confidence

app = FastAPI(title="Sensor Data API", version="1.0.0")


@app.get("/health")
def health():
    """Liveness probe used by Docker and the ALB health check."""
    return {"status": "ok"}


@app.get("/api/anomalies", response_model=list[Anomaly])
def list_anomalies(
    sensor_id: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
):
    """Return anomalies newest first, optionally filtered by sensor_id and/or date range.

    Joins anomalies to sensor_readings to expose sensor_id as a filter and response field.
    All filters are optional — omitting them returns the full paginated set.
    """
    filters = []
    params = []

    if sensor_id:
        filters.append("sr.sensor_id = %s")
        params.append(sensor_id)
    if start:
        filters.append("a.detected_at >= %s")
        params.append(start)
    if end:
        filters.append("a.detected_at <= %s")
        params.append(end)

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    params += [limit, offset]

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT a.id, a.sensor_data_id, sr.sensor_id,
                       a.anomaly_type, a.confidence_score, a.detected_at
                FROM anomalies a
                JOIN sensor_readings sr ON sr.id = a.sensor_data_id
                {where}
                ORDER BY a.detected_at DESC
                LIMIT %s OFFSET %s
                """,
                params,
            )
            rows = cur.fetchall()

    return [
        Anomaly(
            id=r[0], sensor_data_id=r[1], sensor_id=r[2],
            anomaly_type=r[3], confidence_score=r[4],
            confidence_pct=z_to_confidence(r[4]),
            detected_at=r[5],
        )
        for r in rows
    ]
