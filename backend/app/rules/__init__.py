"""
Trading Rules Engine

Centralized configuration for all trading thresholds and parameters.
Replaces hardcoded values across the codebase with version-controlled YAML config.

Usage:
    from app.rules import get_rules
    rules = get_rules()
    risk_pct = rules.position_sizing.default_risk_percent

Features:
- Typed dataclass models for IDE autocomplete
- Caching with TTL for hot reload support
- Schema validation on load
- Version tracking
"""

from app.rules.loader import get_rules, reload_rules
from app.rules.models import TradingRules

__all__ = ["TradingRules", "get_rules", "reload_rules"]
