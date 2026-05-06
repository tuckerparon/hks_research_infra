# ── HUMAN REVIEW ──────────────────────────────────────────
# Reviewer: Tucker Paron
# Date: 2026-05-05
# Changes from AI draft:
#   - Removed tests for /api/readings and /api/stats — endpoints removed
#   - Added z_to_confidence unit tests
# Notes:
# ──────────────────────────────────────────────────────────

import math
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient
from main import app
from utils import z_to_confidence, confidence_pct_to_z

client = TestClient(app)

NOW = datetime(2026, 5, 5, 10, 0, 0, tzinfo=timezone.utc)

# Matches SELECT: a.id, a.sensor_data_id, sr.sensor_id, a.anomaly_type, a.confidence_score, a.detected_at
ANOMALY_ROW = (1, 1, 'sensor_001', 'temperature_spike', 2.5, NOW)


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


# ── z_to_confidence unit tests ────────────────────────────

def test_z_to_confidence_known_values():
    # z=1.96 is the classic 95% threshold
    assert abs(z_to_confidence(1.96) - 95.0) < 0.1
    # z=2.576 is the classic 99% threshold
    assert abs(z_to_confidence(2.576) - 99.0) < 0.1

def test_z_to_confidence_symmetry():
    # Negative z-scores should give the same result as positive
    assert z_to_confidence(-2.0) == z_to_confidence(2.0)

def test_z_to_confidence_zero():
    # z=0 means the value is exactly at the mean — 0% confidence it's anomalous
    assert z_to_confidence(0.0) == 0.0

def test_z_to_confidence_high_z():
    # Very high z-scores should be close to 100%
    assert z_to_confidence(5.0) > 99.99

def test_z_to_confidence_returns_float():
    result = z_to_confidence(3.0)
    assert isinstance(result, float)
    assert 0.0 <= result <= 100.0


# ── confidence_pct_to_z unit tests ───────────────────────

def test_confidence_pct_to_z_known_values():
    assert abs(confidence_pct_to_z(95.0) - 1.96) < 0.01
    assert abs(confidence_pct_to_z(99.0) - 2.576) < 0.01

def test_confidence_pct_to_z_zero():
    assert confidence_pct_to_z(0.0) == 0.0

def test_confidence_pct_to_z_roundtrip():
    for pct in [50.0, 95.0, 99.0, 99.9]:
        assert abs(z_to_confidence(confidence_pct_to_z(pct)) - pct) < 0.01


# ── API endpoint tests ────────────────────────────────────

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
    assert 'confidence_pct' in data[0]
    assert data[0]['confidence_pct'] > 0


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


def test_list_anomalies_filter_by_anomaly_type():
    with mock_db(fetchall=[ANOMALY_ROW]):
        response = client.get('/api/anomalies?anomaly_type=temperature_spike')
    assert response.status_code == 200


def test_list_anomalies_filter_by_min_confidence_pct():
    with mock_db(fetchall=[ANOMALY_ROW]):
        response = client.get('/api/anomalies?min_confidence_pct=95')
    assert response.status_code == 200


def test_list_anomaly_types_returns_list():
    with mock_db(fetchall=[('pressure_anomaly',), ('temperature_spike',)]):
        response = client.get('/api/anomaly-types')
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert 'temperature_spike' in data


def test_list_sensors_returns_list():
    with mock_db(fetchall=[('sensor_001',), ('sensor_002',)]):
        response = client.get('/api/sensors')
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert 'sensor_001' in data


def test_list_anomalies_pagination():
    with mock_db(fetchall=[ANOMALY_ROW]):
        response = client.get('/api/anomalies?limit=10&offset=0')
    assert response.status_code == 200
    assert isinstance(response.json(), list)
