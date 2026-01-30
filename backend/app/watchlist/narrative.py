"""Backward compatibility facade for narrative generation and signal classification.

This module re-exports functions from:
- signal_classifier.py: Signal classification logic
- narrative_generator.py: Narrative text generation

Use specific modules directly for new code.
"""

from __future__ import annotations

# Re-export models (used by both tests and code)
from .models import SignalClassification, SignalStrength, SignalType

# Re-export from narrative_generator
from .narrative_generator import (
    NARRATIVE_TEMPLATES,
    generate_action_plan,
    generate_company_health_bullets,
    generate_headline,
    generate_position_sizing_text,
    generate_special_notes,
    generate_technical_bullets,
)

# Re-export from signal_classifier
from .signal_classifier import classify_signal
from .trading_style import INDEX_ETFS, classify_trading_style

__all__ = [
    # Constants
    "INDEX_ETFS",
    "NARRATIVE_TEMPLATES",
    # Models
    "SignalClassification",
    "SignalStrength",
    "SignalType",
    # Signal classification
    "classify_signal",
    "classify_trading_style",
    # Narrative generation
    "generate_action_plan",
    "generate_company_health_bullets",
    "generate_headline",
    "generate_position_sizing_text",
    "generate_special_notes",
    "generate_technical_bullets",
]
