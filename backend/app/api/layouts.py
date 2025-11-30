"""Page layout customization API."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.logging_config import get_logger
from app.storage import get_storage

logger = get_logger(__name__)

router = APIRouter(prefix="/api/layouts", tags=["layouts"])
storage = get_storage()


class LayoutConfig(BaseModel):
    """Layout configuration (react-grid-layout format)."""

    cards: list[dict[str, Any]]  # [{i: "card-id", x: 0, y: 0, w: 6, h: 2}, ...]


class LayoutResponse(BaseModel):
    """Layout API response."""

    page_name: str
    layout_config: LayoutConfig
    updated_at: str


@router.get("/{page_name}", response_model=LayoutResponse)
async def get_layout(page_name: str) -> LayoutResponse:
    """Get layout for a page."""
    try:
        df = storage.query(
            "SELECT * FROM page_layouts WHERE page_name = ?",
            [page_name],
        )

        if df.is_empty():
            raise HTTPException(status_code=404, detail=f"No custom layout for {page_name}")

        row = df.to_dicts()[0]
        return LayoutResponse(
            page_name=row["page_name"],
            layout_config=row["layout_config"],
            updated_at=row["updated_at"].isoformat(),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get layout for {page_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/{page_name}")
async def save_layout(page_name: str, layout: LayoutConfig) -> dict[str, str]:
    """Save/update layout for a page (upsert)."""
    try:
        layout_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        with storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO page_layouts (id, page_name, layout_config, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (page_name) DO UPDATE SET
                    layout_config = EXCLUDED.layout_config,
                    updated_at = EXCLUDED.updated_at
                """,
                [layout_id, page_name, json.dumps(layout.model_dump()), now, now],
            )
            conn.commit()

        logger.info(f"Saved layout for {page_name}")
        return {"status": "success", "page_name": page_name}
    except Exception as e:
        logger.error(f"Failed to save layout for {page_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{page_name}")
async def reset_layout(page_name: str) -> dict[str, str]:
    """Reset layout to default (delete custom layout)."""
    try:
        with storage.connection() as conn:
            conn.execute(
                "DELETE FROM page_layouts WHERE page_name = ?",
                [page_name],
            )
            conn.commit()

        logger.info(f"Reset layout for {page_name}")
        return {"status": "success", "page_name": page_name, "action": "reset"}
    except Exception as e:
        logger.error(f"Failed to reset layout for {page_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
