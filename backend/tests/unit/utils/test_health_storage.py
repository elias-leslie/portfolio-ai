from __future__ import annotations

from unittest.mock import MagicMock

from app.utils.health_storage import get_api_quotas


def test_get_api_quotas_uses_loaded_quota_config_without_sources_directory(
    monkeypatch,
) -> None:
    storage = MagicMock()
    calls: list[tuple[str, str]] = []

    def fake_load_quota_config() -> dict[str, dict[str, object]]:
        calls.append(("load", "quota_config"))
        return {
            "polygon": {
                "env_var": "POLYGON_API_KEY",
                "rate_limit": "5/min",
                "daily_limit": "100/day",
                "capacity": 100,
            }
        }

    def fake_is_api_key_configured(
        source_id: str,
        env_var: str,
        _storage: MagicMock,
    ) -> bool:
        calls.append((source_id, env_var))
        return True

    monkeypatch.setattr("app.utils.health_storage.load_quota_config", fake_load_quota_config)
    monkeypatch.setattr(
        "app.utils.health_storage.is_api_key_configured",
        fake_is_api_key_configured,
    )

    quotas = get_api_quotas(storage)

    assert calls == [("load", "quota_config"), ("polygon", "POLYGON_API_KEY")]
    assert [quota.model_dump() for quota in quotas] == [
        {
            "source_name": "polygon",
            "configured": True,
            "rate_limit": "5/min",
            "daily_limit": "100/day",
            "estimated_capacity": 100,
        }
    ]
