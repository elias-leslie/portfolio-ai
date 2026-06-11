"""Named allocation scenarios for the retirement allocation lab.

A scenario is a user-defined symbol/weight mix with optional bridge
overrides (growth mode, fixed real return). The lab compares previews of
the real account-derived allocation against these saved what-ifs, so the
rows persist across sessions instead of living only in component state.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from importlib import import_module
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class AllocationScenarioHolding(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=16)
    weight: float = Field(..., gt=0.0)


class AllocationScenarioInput(BaseModel):
    id: str | None = None
    name: str = Field(..., min_length=1, max_length=80)
    holdings: list[AllocationScenarioHolding] = Field(..., min_length=1, max_length=40)
    bridge_growth: Literal["fixed", "portfolio"] | None = None
    bridge_real_return: float | None = Field(None, ge=-0.05, le=0.10)
    notes: str | None = Field(None, max_length=500)


class AllocationScenario(AllocationScenarioInput):
    id: str
    created_at: str
    updated_at: str


class AllocationScenariosReplaceRequest(BaseModel):
    scenarios: list[AllocationScenarioInput] = Field(..., max_length=20)

    @model_validator(mode="after")
    def _unique_names(self) -> AllocationScenariosReplaceRequest:
        names = [s.name.strip().lower() for s in self.scenarios]
        if len(names) != len(set(names)):
            raise ValueError("Scenario names must be unique.")
        return self


_SELECT = (
    "SELECT id, name, holdings, bridge_growth, bridge_real_return, notes, "
    "created_at, updated_at FROM household_retirement_allocation_scenarios "
    "ORDER BY created_at ASC"
)


def _row_to_scenario(row: tuple[Any, ...]) -> AllocationScenario:
    holdings = row[2]
    if isinstance(holdings, str):
        holdings = json.loads(holdings)
    return AllocationScenario(
        id=str(row[0]),
        name=str(row[1]),
        holdings=holdings or [],
        bridge_growth=str(row[3]) if row[3] is not None else None,
        bridge_real_return=float(row[4]) if row[4] is not None else None,
        notes=str(row[5]) if row[5] is not None else None,
        created_at=row[6].isoformat() if row[6] is not None else "",
        updated_at=row[7].isoformat() if row[7] is not None else "",
    )


class AllocationScenariosService:
    """List and replace the saved allocation scenarios."""

    def __init__(self, storage: Any | None = None) -> None:
        self.storage = storage or import_module("app.storage").get_storage()

    def list_scenarios(self) -> list[AllocationScenario]:
        with self.storage.connection() as conn:
            rows = conn.execute(_SELECT).fetchall()
        return [_row_to_scenario(row) for row in rows]

    def replace_scenarios(
        self, payload: AllocationScenariosReplaceRequest
    ) -> list[AllocationScenario]:
        now = datetime.now(UTC)
        with self.storage.connection() as conn:
            existing_ids = {
                str(row[0])
                for row in conn.execute(
                    "SELECT id FROM household_retirement_allocation_scenarios"
                ).fetchall()
            }
            # Delete dropped rows first so a re-created scenario can reuse a
            # freed name without tripping the unique constraint.
            payload_ids = {item.id for item in payload.scenarios if item.id}
            for stale_id in existing_ids - payload_ids:
                conn.execute(
                    "DELETE FROM household_retirement_allocation_scenarios WHERE id = %s",
                    [stale_id],
                )
            for item in payload.scenarios:
                holdings_json = json.dumps([h.model_dump() for h in item.holdings])
                if item.id and item.id in existing_ids:
                    conn.execute(
                        """
                        UPDATE household_retirement_allocation_scenarios
                        SET name = %s, holdings = %s::jsonb, bridge_growth = %s,
                            bridge_real_return = %s, notes = %s, updated_at = %s
                        WHERE id = %s
                        """,
                        [
                            item.name,
                            holdings_json,
                            item.bridge_growth,
                            item.bridge_real_return,
                            item.notes,
                            now,
                            item.id,
                        ],
                    )
                else:
                    new_id = str(uuid.uuid4())
                    conn.execute(
                        """
                        INSERT INTO household_retirement_allocation_scenarios
                            (id, name, holdings, bridge_growth, bridge_real_return,
                             notes, created_at, updated_at)
                        VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s, %s)
                        """,
                        [
                            new_id,
                            item.name,
                            holdings_json,
                            item.bridge_growth,
                            item.bridge_real_return,
                            item.notes,
                            now,
                            now,
                        ],
                    )
            conn.commit()
        return self.list_scenarios()
