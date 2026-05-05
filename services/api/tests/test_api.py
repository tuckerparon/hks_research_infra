# ── HUMAN REVIEW ──────────────────────────────────────────
# Reviewer: Tucker Paron
# Date: 2026-05-05
# Changes from AI draft:
#   - Removed tests for /api/readings and /api/stats — endpoints removed
# Notes:
# ──────────────────────────────────────────────────────────

import os
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

NOW = datetime(2026, 5, 5, 10, 0, 0, tzinfo=timezone.utc)

# Matches SELECT: a.id, a.sensor_data_id, sr.sensor_id, a.anomaly_type, a.confidence_score, a.detected_at
ANOMALY_ROW = (1, 1, 'sensor_001', 'temperature_spike', 0.92, NOW)


@contextmanager
def mock_db(fetchall=None):
    """Patch get_conn with a mock cursor returning preset rows."""
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = lambda s: s
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_cursor.fetchall.return_value = fetchall or []

    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor

    @contextmanager
    def fake_get_conn():
        yield mock_conn

    with patch('main.get_conn', fake_get_conn):
        yield


def test_health():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_list_anomalies_returns_list():
    with mock_db(fetchall=[ANOMALY_ROW]):
        response = client.get('/api/anomalies')
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]['anomaly_type'] == 'temperature_spike'
    assert data[0]['sensor_id'] == 'sensor_001'


def test_list_anomalies_filter_by_sensor_id():
    with mock_db(fetchall=[ANOMALY_ROW]):
        response = client.get('/api/anomalies?sensor_id=sensor_001')
    assert response.status_code == 200


def test_list_anomalies_filter_by_date_range():
    with mock_db(fetchall=[ANOMALY_ROW]):
        response = client.get('/api/anomalies?start=2026-05-05T00:00:00Z&end=2026-05-05T23:59:59Z')
    assert response.status_code == 200


def test_list_anomalies_all_filters_combined():
    with mock_db(fetchall=[ANOMALY_ROW]):
        response = client.get(
            '/api/anomalies?sensor_id=sensor_001&start=2026-05-05T00:00:00Z&end=2026-05-05T23:59:59Z'
        )
    assert response.status_code == 200


def test_list_anomalies_empty():
    with mock_db(fetchall=[]):
        response = client.get('/api/anomalies')
    assert response.status_code == 200
    assert response.json() == []
