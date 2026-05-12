"""Sector cap resolution + helper.

Centralizes reads of ``sector_targets`` for the committee IPS and any
future caller. Precedence (highest priority first):

1. ``sector_targets`` row scoped to ``(household_id, sector)``
2. Global row ``(household_id IS NULL, sector)``
3. Global ``'default'`` row
4. Hardcoded fallback (``RiskManagementRules.max_sector_exposure_pct``
   default = 0.20) — should never fire post-migration since the
   'default' row is seeded.

The YAML rules config + the pydantic model retain the 0.20 value as
project-wide bootstrap; the rules-validator surface still validates
the YAML, but no IPS check reads it directly. This consolidates
fold-in #1 from the subtask-1 audit.
"""

from __future__ import annotations

from app.logging_config import get_logger
from app.storage.connection import get_connection_manager

logger = get_logger(__name__)

# Mirror the YAML + pydantic fallback so the function is self-contained.
# If both DB row + YAML disappear, IPS still has a sane cap.
_HARD_FALLBACK = 0.20


def get_cap(sector: str | None, household_id: str | None) -> float:
    """Resolve the sector cap for (sector, household_id) via the documented precedence."""
    if not sector:
        return _resolve_default(household_id)
    cm = get_connection_manager()
    with cm.connection() as conn:
        if household_id:
            row = conn.execute(
                """
                SELECT max_pct FROM sector_targets
                WHERE sector = %s AND household_id = %s
                """,
                (sector, household_id),
            ).fetchone()
            if row and row[0] is not None:
                return float(row[0])
        row = conn.execute(
            """
            SELECT max_pct FROM sector_targets
            WHERE sector = %s AND household_id IS NULL
            """,
            (sector,),
        ).fetchone()
        if row and row[0] is not None:
            return float(row[0])
    return _resolve_default(household_id)


def _resolve_default(household_id: str | None) -> float:
    """Resolve the 'default' fallback cap. Hits DB once."""
    cm = get_connection_manager()
    with cm.connection() as conn:
        if household_id:
            row = conn.execute(
                """
                SELECT max_pct FROM sector_targets
                WHERE sector = 'default' AND household_id = %s
                """,
                (household_id,),
            ).fetchone()
            if row and row[0] is not None:
                return float(row[0])
        row = conn.execute(
            """
            SELECT max_pct FROM sector_targets
            WHERE sector = 'default' AND household_id IS NULL
            """,
        ).fetchone()
        if row and row[0] is not None:
            return float(row[0])
    return _HARD_FALLBACK
