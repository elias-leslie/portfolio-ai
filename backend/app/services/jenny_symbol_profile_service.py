"""Symbol profile and thesis-preparation helpers for Jenny."""

from __future__ import annotations

from typing import Any

from app.agents.clients.agent_hub_client import AGENT_HUB_ENABLED
from app.logging_config import get_logger
from app.models.thesis import Thesis
from app.watchlist.data_quality import calculate_data_quality, get_security_type

logger = get_logger(__name__)


class JennySymbolProfileService:
    """Prepare symbol metadata before review orchestration runs."""

    def default_symbol_profile(self, service: Any, symbol: str) -> dict[str, Any]:
        security_type = self.normalize_security_type(service, symbol, None)
        return {
            "security_type": security_type,
            "is_passive_fund": security_type == "etf",
            "is_live_position": False,
            "data_quality_pct": None,
        }

    def normalize_security_type(
        self,
        service: Any,
        symbol: str,
        stored_security_type: str | None,
    ) -> str:
        normalized_symbol = symbol.upper()
        normalized_type = (stored_security_type or "").strip().lower()
        if normalized_type == "etf" or normalized_symbol in service.PASSIVE_FUND_SYMBOLS:
            return "etf"
        if normalized_type in {"equity", "index", "other"}:
            return normalized_type
        return "equity"

    def build_symbol_profiles(
        self,
        service: Any,
        symbols: list[str],
        live_symbols: set[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        if not symbols:
            return {}
        live_symbols = live_symbols or set()
        quality_map = calculate_data_quality(service.storage, symbols)
        profiles: dict[str, dict[str, Any]] = {}
        for symbol in symbols:
            security_type = self.normalize_security_type(
                service,
                symbol,
                get_security_type(service.storage, symbol),
            )
            quality = quality_map.get(symbol)
            profiles[symbol] = {
                "security_type": security_type,
                "is_passive_fund": security_type == "etf",
                "is_live_position": symbol in live_symbols,
                "data_quality_pct": quality.overall_pct if quality else None,
            }
        return profiles

    def ensure_thesis(
        self,
        service: Any,
        symbol: str,
        symbol_profile: dict[str, Any],
    ) -> Thesis | None:
        thesis = service.thesis_service.get_thesis(symbol)
        if thesis is not None:
            return thesis
        if symbol_profile.get("is_passive_fund"):
            return None
        data_quality_pct = symbol_profile.get("data_quality_pct")
        if data_quality_pct is not None and data_quality_pct < service.MIN_AGENT_REVIEW_DATA_QUALITY_PCT:
            return None
        if not AGENT_HUB_ENABLED:
            return None
        try:
            return service.thesis_service.generate_thesis(symbol, force=False)
        except Exception as exc:
            logger.warning("jenny_thesis_generation_skipped", symbol=symbol, error=str(exc))
            return None
