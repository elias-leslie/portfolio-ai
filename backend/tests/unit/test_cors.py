"""Unit tests for CORS origin construction."""

from __future__ import annotations

from app.config.cors import build_cors_origins


def test_build_cors_origins_defaults_to_localhost_only() -> None:
    origins = build_cors_origins()

    assert origins == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://localhost:3000",
        "https://127.0.0.1:3000",
    ]


def test_build_cors_origins_adds_optional_hosts_and_extra_origins() -> None:
    origins = build_cors_origins(
        frontend_host="192.168.1.100",
        extra_origins="https://portfolio.example.com, https://portfolio.example.com",
    )

    assert "http://192.168.1.100:3000" in origins
    assert "https://192.168.1.100:3000" in origins
    assert "https://portfolio.example.com" in origins
    assert origins.count("https://portfolio.example.com") == 1


def test_build_cors_origins_respects_custom_port() -> None:
    origins = build_cors_origins(frontend_url="http://localhost:4000")

    assert "http://localhost:4000" in origins
    assert "http://127.0.0.1:4000" in origins
    assert "http://localhost:3000" not in origins
