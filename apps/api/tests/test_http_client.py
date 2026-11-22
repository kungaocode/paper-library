from __future__ import annotations

from app.http_client import normalize_proxy_url, proxy_url_from_env


def test_normalize_proxy_url_rewrites_socks_alias() -> None:
    assert normalize_proxy_url("socks://127.0.0.1:7897") == (
        "socks5://127.0.0.1:7897"
    )
    assert normalize_proxy_url("http://127.0.0.1:7897") == (
        "http://127.0.0.1:7897"
    )


def test_proxy_url_from_env_prefers_https_proxy(monkeypatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:7897")
    monkeypatch.setenv("ALL_PROXY", "socks://127.0.0.1:7898")
    assert proxy_url_from_env() == "http://127.0.0.1:7897"


def test_proxy_url_from_env_normalizes_all_proxy(monkeypatch) -> None:
    for name in (
        "HTTPS_PROXY",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
        "HTTP_PROXY",
        "http_proxy",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ALL_PROXY", "socks://127.0.0.1:7897")
    assert proxy_url_from_env() == "socks5://127.0.0.1:7897"
