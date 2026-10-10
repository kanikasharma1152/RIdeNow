"""
Tests for Phase 3 — ML Layer
=============================
Covers:
  - Demand predictor (rule-based scoring, zone snapping, hotspots fallback)
  - ETA predictor (haversine fallback, congestion application, output shape)
  - Anomaly detector (route deviation, long stop, speed anomaly, composite)
  - Smart matching engine (scoring, ranking, exclusions, no-candidates)
  - ML router endpoints (demand, eta, info)
  - ride.py integration (find_next_available_driver uses ML engine)
"""

import math
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


# ─── Demand Predictor ─────────────────────────────────────────────────────────

class TestDemandPredictor:
    """Tests for backend/app/ml/demand/predictor.py"""

    def test_zone_key_snapping(self):
        from app.ml.demand.predictor import _zone_key, GRID_RESOLUTION
        lat, lon = 22.7196, 75.8577  # Indore
        zk = _zone_key(lat, lon)
        # Result should be a multiple of GRID_RESOLUTION
        assert abs(zk[0] % GRID_RESOLUTION) < 1e-9 or abs(zk[0] % GRID_RESOLUTION - GRID_RESOLUTION) < 1e-9
        assert isinstance(zk, tuple) and len(zk) == 2

    def test_time_demand_factor_peak_hour(self):
        from app.ml.demand.predictor import HOUR_MULTIPLIER, DAY_MULTIPLIER
        # 18:00 Friday should give highest factor
        hour_factor = HOUR_MULTIPLIER[18]  # 2.2
        day_factor = DAY_MULTIPLIER[4]    # Friday = 1.3
        score = hour_factor * day_factor
        assert score > 2.0, f"Peak hour score should be >2.0, got {score}"

    def test_demand_label_low(self):
        from app.ml.demand.predictor import _demand_label
        assert _demand_label(0.5) == "LOW"

    def test_demand_label_medium(self):
        from app.ml.demand.predictor import _demand_label
        assert _demand_label(1.2) == "MEDIUM"

    def test_demand_label_high(self):
        from app.ml.demand.predictor import _demand_label
        assert _demand_label(2.5) == "HIGH"

    @pytest.mark.asyncio
    async def test_predict_zone_demand_no_db(self):
        from app.ml.demand.predictor import predict_zone_demand
        # No DB — should still work with rule-based only
        result = await predict_zone_demand(lat=22.7196, lon=75.8577, db=None)
        assert "demand_level" in result
        assert result["demand_level"] in ("LOW", "MEDIUM", "HIGH")
        assert "demand_score" in result
        assert result["method"] == "rule_based"
        assert "zone" in result

    @pytest.mark.asyncio
    async def test_get_demand_hotspots_no_data(self):
        from app.ml.demand.predictor import get_demand_hotspots
        # Mock DB that returns no rows
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_db.execute = AsyncMock(return_value=mock_result)
        result = await get_demand_hotspots(db=mock_db, limit=5)
        # Should return empty list gracefully (DB query may fail or return nothing)
        assert isinstance(result, list)


# ─── ETA Predictor ────────────────────────────────────────────────────────────

class TestETAPredictor:
    """Tests for backend/app/ml/eta/predictor.py"""

    def test_haversine_known_distance(self):
        from app.ml.eta.predictor import _haversine as eta_haversine
        # Approximate distance between two points ~1km apart
        d = eta_haversine(22.7196, 75.8577, 22.7286, 75.8577)
        assert 0.9 < d < 1.1, f"Expected ~1km, got {d}"

    def test_congestion_peak(self):
        from app.ml.eta.predictor import CONGESTION_FACTOR
        assert CONGESTION_FACTOR[18] >= 2.0, "Evening peak should have congestion ≥ 2.0"
        assert CONGESTION_FACTOR[3] == 1.0, "Night should have no congestion"


    @pytest.mark.asyncio
    async def test_predict_eta_no_osrm_no_db(self):
        """ETA fallback when OSRM and DB unavailable."""
        from app.ml.eta.predictor import predict_eta

        with patch("app.ml.eta.predictor._osrm_route", return_value=None):
            result = await predict_eta(
                pickup_lat=22.7196, pickup_lon=75.8577,
                dropoff_lat=22.7286, dropoff_lon=75.8677,
                db=None,
            )

        assert "trip_eta_minutes" in result
        assert result["trip_eta_minutes"] > 0
        assert "driver_pickup_eta_minutes" in result
        assert result["method"] in ("rule_based", "osrm_corrected")

    @pytest.mark.asyncio
    async def test_predict_eta_with_driver_location(self):
        from app.ml.eta.predictor import predict_eta

        with patch("app.ml.eta.predictor._osrm_route", return_value=None):
            result = await predict_eta(
                pickup_lat=22.7196, pickup_lon=75.8577,
                dropoff_lat=22.7500, dropoff_lon=75.9000,
                driver_lat=22.7100, driver_lon=75.8500,
                db=None,
            )

        assert result["total_eta_minutes"] > 0
        assert result["driver_distance_km"] is not None
        assert result["driver_pickup_eta_minutes"] > 0

    @pytest.mark.asyncio
    async def test_predict_eta_output_keys(self):
        from app.ml.eta.predictor import predict_eta

        with patch("app.ml.eta.predictor._osrm_route", return_value=None):
            result = await predict_eta(
                pickup_lat=22.72, pickup_lon=75.86,
                dropoff_lat=22.74, dropoff_lon=75.88,
            )

        required_keys = [
            "driver_pickup_eta_minutes", "trip_eta_minutes", "total_eta_minutes",
            "trip_distance_km", "congestion_factor", "historical_correction",
            "method", "confidence",
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"


# ─── Anomaly Detector ─────────────────────────────────────────────────────────

class TestAnomalyDetector:
    """Tests for backend/app/ml/anomaly/detector.py"""

    def test_no_deviation_on_route(self):
        from app.ml.anomaly.detector import check_route_deviation
        waypoints = [(22.72, 75.86), (22.73, 75.87), (22.74, 75.88)]
        # Current position exactly on a waypoint
        result = check_route_deviation(22.73, 75.87, waypoints)
        assert result["is_deviated"] is False
        assert result["min_distance_km"] < 0.1

    def test_deviation_detected(self):
        from app.ml.anomaly.detector import check_route_deviation
        waypoints = [(22.72, 75.86), (22.73, 75.87), (22.74, 75.88)]
        # Position 5km off route
        result = check_route_deviation(22.80, 76.00, waypoints)
        assert result["is_deviated"] is True
        assert result["anomaly_type"] == "ROUTE_DEVIATION"
        assert result["severity"] in ("LOW", "MEDIUM", "HIGH")

    def test_insufficient_waypoints(self):
        from app.ml.anomaly.detector import check_route_deviation
        result = check_route_deviation(22.72, 75.86, [])
        assert result["is_deviated"] is False
        assert "insufficient_waypoints" in result.get("note", "")

    def test_long_stop_detected(self):
        from app.ml.anomaly.detector import check_long_stop
        old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        result = check_long_stop(
            last_position_update=old_time,
            last_lat=22.72, last_lon=75.86,
            current_lat=22.72, current_lon=75.86,  # hasn't moved
        )
        assert result["is_long_stop"] is True
        assert result["anomaly_type"] == "LONG_STOP"

    def test_no_long_stop_when_moving(self):
        from app.ml.anomaly.detector import check_long_stop
        old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        result = check_long_stop(
            last_position_update=old_time,
            last_lat=22.72, last_lon=75.86,
            current_lat=22.75, current_lon=75.90,  # moved significantly
        )
        assert result["is_long_stop"] is False

    def test_speed_anomaly_detected(self):
        from app.ml.anomaly.detector import check_speed_anomaly
        now = datetime.now(timezone.utc)
        prev_time = now - timedelta(seconds=10)
        # 10 km in 10 seconds = 3600 km/h → anomaly
        result = check_speed_anomaly(
            prev_lat=22.72, prev_lon=75.86,
            prev_time=prev_time,
            curr_lat=22.82, curr_lon=75.86,
            curr_time=now,
        )
        assert result["is_anomalous"] is True
        assert result["anomaly_type"] == "SPEED_ANOMALY"

    def test_normal_speed_no_anomaly(self):
        from app.ml.anomaly.detector import check_speed_anomaly
        now = datetime.now(timezone.utc)
        prev_time = now - timedelta(seconds=60)
        # ~0.5 km in 60 seconds = 30 km/h → normal
        result = check_speed_anomaly(
            prev_lat=22.72, prev_lon=75.86,
            prev_time=prev_time,
            curr_lat=22.7245, curr_lon=75.86,
            curr_time=now,
        )
        assert result["is_anomalous"] is False

    def test_composite_safety_check_clean(self):
        from app.ml.anomaly.detector import run_safety_checks
        waypoints = [(22.72, 75.86), (22.73, 75.87)]
        now = datetime.now(timezone.utc)
        result = run_safety_checks(
            current_lat=22.725, current_lon=75.865,
            current_time=now,
            route_waypoints=waypoints,
            prev_lat=22.72, prev_lon=75.86,
            prev_time=now - timedelta(seconds=30),
            last_position_update=now - timedelta(seconds=30),
        )
        assert "safe" in result
        assert "anomalies" in result
        assert "checks" in result

    def test_composite_safety_check_deviation(self):
        from app.ml.anomaly.detector import run_safety_checks
        waypoints = [(22.72, 75.86), (22.73, 75.87)]
        now = datetime.now(timezone.utc)
        result = run_safety_checks(
            current_lat=22.90, current_lon=76.20,  # far off route
            current_time=now,
            route_waypoints=waypoints,
        )
        assert result["safe"] is False
        assert len(result["anomalies"]) > 0


# ─── Smart Matching Engine ────────────────────────────────────────────────────

class TestMatchingEngine:
    """Tests for backend/app/ml/matching/engine.py"""

    def _make_driver(self, driver_id, user_id, lat, lon, online=True, available=True):
        d = MagicMock()
        d.id = driver_id
        d.user_id = user_id
        d.latitude = lat
        d.longitude = lon
        d.is_online = online
        d.is_available = available
        return d

    def test_haversine_accuracy(self):
        from app.ml.matching.engine import _haversine_km
        # Known: ~1 degree of latitude ≈ 111 km
        d = _haversine_km(0, 0, 1, 0)
        assert 110 < d < 112, f"Expected ~111 km, got {d}"

    def test_normalize_inverse(self):
        from app.ml.matching.engine import _normalize_inverse
        assert _normalize_inverse(0, 10) == 1.0
        assert _normalize_inverse(10, 10) == 0.0
        # 6/10 = 0.4 exactly — use >= instead of strict >
        assert 0.4 <= _normalize_inverse(6, 10) <= 0.6

    def test_normalize(self):
        from app.ml.matching.engine import _normalize
        assert _normalize(5, 1, 5) == 1.0
        assert _normalize(1, 1, 5) == 0.0
        assert abs(_normalize(3, 1, 5) - 0.5) < 0.01

    @pytest.mark.asyncio
    async def test_rank_drivers_returns_sorted(self):
        from app.ml.matching.engine import rank_drivers

        # Driver A: 1km away, Driver B: 5km away
        d_a = self._make_driver(1, 10, 22.7186, 75.8577)
        d_b = self._make_driver(2, 20, 22.7696, 75.8577)

        results = await rank_drivers(
            drivers=[d_b, d_a],  # B first in list, A should win score
            pickup_lat=22.7196, pickup_lon=75.8577,
            db=None,
        )

        assert len(results) == 2
        assert results[0].driver_id == 1, "Closer driver should rank first"
        assert results[0].total_score > results[1].total_score

    @pytest.mark.asyncio
    async def test_rank_drivers_excludes_ids(self):
        from app.ml.matching.engine import rank_drivers

        d_a = self._make_driver(1, 10, 22.719, 75.857)
        d_b = self._make_driver(2, 20, 22.720, 75.858)

        results = await rank_drivers(
            drivers=[d_a, d_b],
            pickup_lat=22.7196, pickup_lon=75.8577,
            excluded_ids={1},
            db=None,
        )

        assert len(results) == 1
        assert results[0].driver_id == 2

    @pytest.mark.asyncio
    async def test_rank_drivers_no_eligible(self):
        from app.ml.matching.engine import rank_drivers

        d = self._make_driver(1, 10, None, None)
        d.latitude = None
        results = await rank_drivers(
            drivers=[d],
            pickup_lat=22.72, pickup_lon=75.86,
            db=None,
        )
        assert results == []

    @pytest.mark.asyncio
    async def test_find_best_driver(self):
        from app.ml.matching.engine import find_best_driver

        d_a = self._make_driver(1, 10, 22.7190, 75.8570)
        d_b = self._make_driver(2, 20, 22.7900, 75.9000)

        best = await find_best_driver(
            drivers=[d_a, d_b],
            pickup_lat=22.7196, pickup_lon=75.8577,
            db=None,
        )
        assert best is not None
        assert best.id == 1

    @pytest.mark.asyncio
    async def test_find_best_driver_no_candidates(self):
        from app.ml.matching.engine import find_best_driver
        best = await find_best_driver(drivers=[], pickup_lat=22.72, pickup_lon=75.86)
        assert best is None

    def test_score_breakdown_keys(self):
        from app.ml.matching.engine import _score_candidates, DriverCandidate
        c = DriverCandidate(driver_id=1, user_id=10, latitude=22.719, longitude=75.857)
        results = _score_candidates([c], pickup_lat=22.720, pickup_lon=75.858)
        assert len(results) == 1
        r = results[0]
        for key in ("distance_score", "eta_score", "rating_score", "acceptance_score"):
            assert key in r.breakdown

    @pytest.mark.asyncio
    async def test_offline_driver_excluded(self):
        from app.ml.matching.engine import rank_drivers

        d_online = self._make_driver(1, 10, 22.719, 75.857, online=True, available=True)
        d_offline = self._make_driver(2, 20, 22.720, 75.858, online=False, available=True)

        results = await rank_drivers(
            drivers=[d_online, d_offline],
            pickup_lat=22.720, pickup_lon=75.858,
            db=None,
        )
        assert all(r.driver_id != 2 for r in results)


# ─── ML Router Endpoints ──────────────────────────────────────────────────────

async def _ml_register_and_login(client, prefix: str):
    """Helper: register user and return Bearer token."""
    import random, string
    suffix = "".join(random.choices(string.ascii_lowercase, k=6))
    phone_suffix = "".join(random.choices(string.digits, k=7))
    email = f"{prefix}_{suffix}@test.com"
    phone = f"99{phone_suffix}"  # unique 9-digit phone

    reg = await client.post("/users/register", json={
        "name": f"ML {prefix} Test",
        "email": email,
        "phone": phone,
        "password": "Test1234!",
        "role": "passenger",
    })
    # Accept 200 or 201 for success
    assert reg.status_code in (200, 201), f"Register failed ({reg.status_code}): {reg.text}"

    login = await client.post(
        "/users/login",
        data={"username": email, "password": "Test1234!"},
    )
    assert login.status_code == 200, f"Login failed: {login.text}"
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_ml_unauthenticated_demand(client):
    """Unauthenticated request to /ml/demand should return 401."""
    resp = await client.get("/ml/demand?lat=22.72&lon=75.86")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_ml_info_authenticated(client):
    """Authenticated user can access /ml/info."""
    headers = await _ml_register_and_login(client, "mlinfo")

    resp = await client.get("/ml/info", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "demand_model" in data["data"]
    assert "driver_matching" in data["data"]


@pytest.mark.asyncio
async def test_ml_demand_endpoint(client):
    """Authenticated demand prediction returns correct structure."""
    headers = await _ml_register_and_login(client, "mldemand")

    resp = await client.get("/ml/demand?lat=22.7196&lon=75.8577", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["demand_level"] in ("LOW", "MEDIUM", "HIGH")
    assert "demand_score" in data["data"]
    assert data["data"]["method"] == "rule_based"


@pytest.mark.asyncio
async def test_ml_hotspots_endpoint(client):
    """Hotspots endpoint returns list (may be empty for fresh test DB)."""
    headers = await _ml_register_and_login(client, "mlhot")

    resp = await client.get("/ml/demand/hotspots?limit=3", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "count" in data
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_ml_eta_endpoint(client):
    """ETA prediction returns positive minutes for valid coordinates."""
    headers = await _ml_register_and_login(client, "mleta")

    with patch("app.ml.eta.predictor._osrm_route", return_value=None):
        resp = await client.get(
            "/ml/eta?pickup_lat=22.72&pickup_lon=75.86&dropoff_lat=22.74&dropoff_lon=75.88",
            headers=headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["trip_eta_minutes"] > 0
