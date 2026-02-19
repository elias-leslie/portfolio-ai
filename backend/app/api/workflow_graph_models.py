"""Pydantic models for the Workflow Graph API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class NodeData(BaseModel):
    """Data payload for a workflow node."""

    label: str
    schedule: str
    category: str
    status: Literal["idle", "running", "completed", "failed", "pending"]
    lastRun: str | None  # noqa: N815 - camelCase for frontend API
    nextRun: str | None  # noqa: N815 - camelCase for frontend API
    successRate: float  # noqa: N815 - camelCase for frontend API
    avgDuration: float  # noqa: N815 - camelCase for frontend API (milliseconds)
    populatesTables: list[str]  # noqa: N815 - camelCase for frontend API


class WorkflowNode(BaseModel):
    """A node in the workflow graph."""

    id: str
    type: Literal["task", "workflow", "agent"]
    data: NodeData
    position: dict[str, float]


class WorkflowEdge(BaseModel):
    """An edge connecting two nodes."""

    id: str
    source: str
    target: str
    type: Literal["dependency", "data-flow"]
    animated: bool = False


class WorkflowGraphResponse(BaseModel):
    """Response model for workflow graph endpoint."""

    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]
    categories: list[str]
    lastUpdated: str  # noqa: N815 - camelCase for frontend API


class DependencyOverrideRequest(BaseModel):
    """Request model for updating task dependency overrides."""

    add: list[str] = []
    remove: list[str] = []
    reason: str


class DependencyOverrideResponse(BaseModel):
    """Response model for dependency override updates."""

    status: str
    task_name: str
    overrides: dict[str, Any]
