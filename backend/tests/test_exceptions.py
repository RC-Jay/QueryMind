from fastapi.testclient import TestClient
from exceptions import (
    AppError, ValidationError, AuthError, InvalidTokenError,
    ForbiddenError, NotFoundError, ConflictError, ServiceUnavailableError,
)
from main import app


def test_status_codes():
    assert ValidationError("x").status_code == 400
    assert AuthError("x").status_code == 401
    assert InvalidTokenError("x").status_code == 401
    assert ForbiddenError("x").status_code == 403
    assert NotFoundError("x").status_code == 404
    assert ConflictError("x").status_code == 409
    assert ServiceUnavailableError("x").status_code == 503


def test_invalid_token_is_auth_error():
    assert issubclass(InvalidTokenError, AuthError)
    assert issubclass(AuthError, AppError)


def test_detail_carried():
    assert AppError("boom").detail == "boom"


# ── central handler mapping (in-process, no server) ───────────────────────────

def test_bad_token_maps_to_401():
    client = TestClient(app)
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401
    assert "detail" in r.json()


def test_health_ok():
    client = TestClient(app)
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
