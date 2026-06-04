from fastapi.testclient import TestClient
from main import app


def test_health_is_live():
    r = TestClient(app).get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_request_id_header_present():
    r = TestClient(app).get("/api/health")
    assert r.headers.get("X-Request-ID")  # middleware tagged the response


def test_request_id_echoed_from_inbound_header():
    r = TestClient(app).get("/api/health", headers={"X-Request-ID": "trace-123"})
    assert r.headers.get("X-Request-ID") == "trace-123"


def test_readyz_ok_when_analytics_db_reachable():
    # In tests: analytics DB = in-memory/SQLite SELECT 1 works; business DB
    # not configured; Redis falls back in-process → overall ready.
    r = TestClient(app).get("/api/readyz")
    assert r.status_code == 200
    body = r.json()
    assert body["ready"] is True
    assert body["checks"]["analytics_db"] == "ok"
    assert body["checks"]["business_db"] == "not_configured"
