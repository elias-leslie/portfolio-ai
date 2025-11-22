"""Trading Intelligence Gap Detection.

This package provides gap detection capabilities by comparing trading requirements
against available system capabilities.

Main exports:
- GapDetector: Main facade for gap detection
- Type definitions: GapAnalysisResult, GapInfo, CoverageResult, etc.
"""

from .gap_detector import GapDetector
from .types import (
    CapabilityRequirement,
    CoverageResult,
    GapAnalysisResult,
    GapInfo,
)

__all__ = [
    "CapabilityRequirement",
    "CoverageResult",
    "GapAnalysisResult",
    "GapDetector",
    "GapInfo",
]
