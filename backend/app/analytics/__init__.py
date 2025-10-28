"""Analytics module for trading intelligence and market analysis.

This module provides analytical functions for:
- Volume analysis (RVOL)
- Sector rotation
- Peer comparison
- Technical indicators
"""

from __future__ import annotations

from .peers import get_peer_comparison, get_peer_group_detail
from .sectors import get_sector_performance_detail, get_sector_rotation
from .volume import calculate_rvol, get_high_volume_tickers

__all__ = [
    "calculate_rvol",
    "get_high_volume_tickers",
    "get_sector_rotation",
    "get_sector_performance_detail",
    "get_peer_comparison",
    "get_peer_group_detail",
]
