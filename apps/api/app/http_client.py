from __future__ import annotations

import os


def normalize_proxy_url(value: str) -> str:
    """Normalize the SOCKS alias used by some shells to httpx's socks5 scheme."""
    proxy = value.strip()
    if proxy.lower().startswith("socks://"):
        return f"socks5://{proxy[len('socks://'):]}"
    return proxy


def proxy_url_from_env() -> str | None:
    """Return the first configured standard proxy without parsing ALL_PROXY directly."""
    for name in (
        "HTTPS_PROXY",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
        "HTTP_PROXY",
        "http_proxy",
    ):
        value = os.getenv(name)
        if value and value.strip():
            return normalize_proxy_url(value)
    return None
