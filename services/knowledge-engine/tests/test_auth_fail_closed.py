"""Security tests for the Intelos authentication defaults."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth import PasswordAuthMiddleware


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(PasswordAuthMiddleware)

    @app.get("/private")
    async def private_endpoint() -> dict[str, bool]:
        return {"ok": True}

    return app


def _clear_password(monkeypatch) -> None:
    monkeypatch.delenv("OPEN_NOTEBOOK_PASSWORD", raising=False)
    monkeypatch.delenv("OPEN_NOTEBOOK_PASSWORD_FILE", raising=False)


def test_missing_password_fails_closed(monkeypatch):
    _clear_password(monkeypatch)
    monkeypatch.setenv("OPEN_NOTEBOOK_ALLOW_NO_AUTH", "false")

    with TestClient(_build_app()) as client:
        response = client.get("/private")

    assert response.status_code == 503
    assert "Authentication is not configured" in response.json()["detail"]


def test_passwordless_access_requires_explicit_opt_out(monkeypatch):
    _clear_password(monkeypatch)
    monkeypatch.setenv("OPEN_NOTEBOOK_ALLOW_NO_AUTH", "true")

    with TestClient(_build_app()) as client:
        response = client.get("/private")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_configured_password_is_required_and_accepted(monkeypatch):
    monkeypatch.delenv("OPEN_NOTEBOOK_PASSWORD_FILE", raising=False)
    monkeypatch.setenv("OPEN_NOTEBOOK_PASSWORD", "test-password")
    monkeypatch.setenv("OPEN_NOTEBOOK_ALLOW_NO_AUTH", "false")

    with TestClient(_build_app()) as client:
        unauthenticated = client.get("/private")
        authenticated = client.get(
            "/private", headers={"Authorization": "Bearer test-password"}
        )

    assert unauthenticated.status_code == 401
    assert authenticated.status_code == 200
    assert authenticated.json() == {"ok": True}
