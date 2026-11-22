from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from .config import Settings


SESSION_COOKIE_NAME = "paper_session"
_TOKEN_VERSION = 1


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")


def verify_credentials(settings: Settings, username: str, password: str) -> bool:
    return hmac.compare_digest(username, settings.auth_username) and hmac.compare_digest(
        password, settings.auth_password
    )


def create_session_token(
    settings: Settings,
    username: str,
    now: int | None = None,
) -> str:
    issued_at = int(time.time() if now is None else now)
    payload = json.dumps(
        {
            "exp": issued_at + settings.auth_session_ttl_hours * 3600,
            "sub": username,
            "v": _TOKEN_VERSION,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    signature = hmac.new(
        settings.auth_signing_key.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).digest()
    return f"{_base64url_encode(payload)}.{_base64url_encode(signature)}"


def verify_session_token(
    settings: Settings,
    token: str | None,
    now: int | None = None,
) -> bool:
    if not token or not settings.auth_enabled:
        return False

    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        payload = _base64url_decode(encoded_payload)
        signature = _base64url_decode(encoded_signature)
    except (ValueError, TypeError):
        return False

    expected_signature = hmac.new(
        settings.auth_signing_key.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(signature, expected_signature):
        return False

    try:
        claims = json.loads(payload)
        expires_at = int(claims["exp"])
        username = str(claims["sub"])
        version = int(claims["v"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False

    current_time = int(time.time() if now is None else now)
    return (
        version == _TOKEN_VERSION
        and expires_at > current_time
        and hmac.compare_digest(username, settings.auth_username)
    )
