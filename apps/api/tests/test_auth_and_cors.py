from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import create_session_token, verify_session_token
from app.config import Settings
from app.main import create_app


def build_settings(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "paper_root": tmp_path,
        "storage_dir": tmp_path / "storage" / "api",
        "llm_provider": "mock",
        "llm_base_url": "",
        "llm_api_key": "",
        "llm_model": "mock",
        "llm_timeout_seconds": 10,
        "llm_max_output_tokens": 2000,
        "llm_json_mode": True,
        "allow_private_urls": False,
        "max_download_mb": 20,
        "max_text_chars": 30000,
        "analysis_page_limit": 8,
    }
    values.update(overrides)
    return Settings(**values)


def test_optional_auth_protects_api_routes(tmp_path: Path) -> None:
    settings = build_settings(
        tmp_path,
        auth_username="researcher",
        auth_password="secret-password",
        auth_session_secret="test-signing-secret",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/auth/status").json() == {
            "auth_enabled": True,
            "authenticated": False,
            "username": "",
        }
        assert client.get("/api/settings/models").status_code == 401
        assert (
            client.post(
                "/api/auth/login",
                json={"username": "researcher", "password": "wrong"},
            ).status_code
            == 401
        )

        login_response = client.post(
            "/api/auth/login",
            json={"username": "researcher", "password": "secret-password"},
        )
        assert login_response.status_code == 200
        assert login_response.json()["authenticated"] is True
        assert "paper_session" in client.cookies
        assert client.get("/api/settings/models").status_code == 200

        logout_response = client.post("/api/auth/logout")
        assert logout_response.status_code == 204
        assert client.get("/api/settings/models").status_code == 401


def test_auth_can_be_disabled_for_trusted_lan_preview(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    app = create_app(settings)

    with TestClient(app) as client:
        assert client.get("/api/settings/models").status_code == 200
        status = client.get("/api/auth/status").json()
        assert status["auth_enabled"] is False
        assert status["authenticated"] is True

        login_response = client.post(
            "/api/auth/login",
            json={"username": "preview", "password": "anything"},
        )
        assert login_response.status_code == 200
        assert login_response.cookies["paper_session"] == "preview"


def test_session_token_rejects_expired_or_tampered_values(tmp_path: Path) -> None:
    settings = build_settings(
        tmp_path,
        auth_password="secret-password",
        auth_session_secret="test-signing-secret",
        auth_session_ttl_hours=1,
    )
    token = create_session_token(settings, "admin", now=1_000)

    assert verify_session_token(settings, token, now=1_001) is True
    assert verify_session_token(settings, token, now=4_601) is False
    assert verify_session_token(settings, f"{token}x", now=1_001) is False


def test_cors_origins_are_loaded_from_settings(tmp_path: Path) -> None:
    allowed_origin = "http://192.168.1.20:3000"
    settings = build_settings(
        tmp_path,
        cors_origins=(allowed_origin,),
        auth_password="secret-password",
        auth_session_secret="test-signing-secret",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.options(
            "/api/categories",
            headers={
                "Origin": allowed_origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == allowed_origin
        assert response.headers["access-control-allow-credentials"] == "true"

        unauthorized = client.get(
            "/api/settings/models",
            headers={"Origin": allowed_origin},
        )
        assert unauthorized.status_code == 401
        assert unauthorized.headers["access-control-allow-origin"] == allowed_origin

        blocked = client.options(
            "/api/categories",
            headers={
                "Origin": "http://untrusted.example:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" not in blocked.headers


def test_auth_and_cors_settings_are_read_from_environment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PAPER_ROOT", str(tmp_path))
    monkeypatch.setenv("CORS_ORIGINS", "http://10.0.0.8:3000, http://10.0.0.8:3001/")
    monkeypatch.setenv("AUTH_USERNAME", "internal-user")
    monkeypatch.setenv("AUTH_PASSWORD", "env-password")
    monkeypatch.setenv("AUTH_SESSION_SECRET", "env-signing-secret")
    monkeypatch.setenv("AUTH_SESSION_TTL_HOURS", "12")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")

    settings = Settings.from_env()

    assert settings.cors_origins == (
        "http://10.0.0.8:3000",
        "http://10.0.0.8:3001",
    )
    assert settings.auth_username == "internal-user"
    assert settings.auth_password == "env-password"
    assert settings.auth_session_secret == "env-signing-secret"
    assert settings.auth_session_ttl_hours == 12
    assert settings.auth_cookie_secure is True
