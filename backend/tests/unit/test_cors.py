"""Unit tests for CORS origin construction."""

from __future__ import annotations

from app.config.cors import build_cors_origins


def test_build_cors_origins_defaults_to_localhost_and_production() -> None:
    origins = build_cors_origins()

    assert origins == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://localhost:3000",
        "https://127.0.0.1:3000",
        "https://port.summitflow.dev",
    ]


def test_build_cors_origins_adds_optional_hosts_and_extra_origins() -> None:
    origins = build_cors_origins(
        frontend_host="192.168.8.233",
        extra_origins="https://portfolio.example.com, https://port.summitflow.dev",
    )

    assert "http://192.168.8.233:3000" in origins
    assert "https://192.168.8.233:3000" in origins
    assert "https://portfolio.example.com" in origins
    assert origins.count("https://port.summitflow.dev") == 1
