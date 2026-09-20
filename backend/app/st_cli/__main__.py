"""Independent entry point for the Portfolio AI-owned ST command."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from st_sdk.runtime import run_app

from .portfolio import app


def main(args: Sequence[str] | None = None) -> Any:
    return run_app(app, "portfolio", args)


if __name__ == "__main__":
    main()

