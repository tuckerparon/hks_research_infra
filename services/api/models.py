# ── HUMAN REVIEW ──────────────────────────────────────────
# Reviewer: Tucker Paron
# Date: 2026-05-05
# Changes from AI draft:
#   - Removed SensorReading and Stats — not required by README. Requirements only specify wanting anomaly data.
# Notes:
#   - Each model defines the shape of an API response; FastAPI validates and serializes automatically
# ──────────────────────────────────────────────────────────

from datetime import datetime
from pydantic import BaseModel


class Anomaly(BaseModel):
    id: int
    sensor_data_id: int
    sensor_id: str
    anomaly_type: str
    confidence_score: float
    detected_at: datetime
