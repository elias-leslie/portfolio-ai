"""Shared Pydantic input/output models for Hatchet workflows."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class EmptyInput(BaseModel):
    pass


class SymbolInput(BaseModel):
    symbol: str


class SymbolsInput(BaseModel):
    symbols: list[str]
    days: int | None = None


class StrategyInput(BaseModel):
    strategy_id: str
    symbol: str | None = None


class SeedInput(BaseModel):
    seed_id: str
    symbol: str


class InsightInput(BaseModel):
    output: str
    context_type: str = "insight"
    symbol: str | None = None
    confidence: float | None = None


class EventInput(BaseModel):
    event_type: str
    payload: dict[str, Any]


class CleanupInput(BaseModel):
    days: int | None = None
    dry_run: bool = False


class BackfillInput(BaseModel):
    symbol: str | None = None
    days: int | None = None


class AgentInput(BaseModel):
    agent_type: str = "discovery"
    symbol: str | None = None


class WatchlistInput(BaseModel):
    symbol: str | None = None
    user_id: str = "default"
