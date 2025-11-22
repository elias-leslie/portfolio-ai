"""Requirements loader for gap detection."""

from __future__ import annotations

import pathlib
from typing import Any

import yaml

from ...logging_config import get_logger

logger = get_logger(__name__)


class RequirementsLoader:
    """Loads and provides access to trading requirements."""

    def __init__(self, requirements_path: str | pathlib.Path | None = None) -> None:
        """Initialize requirements loader.

        Args:
            requirements_path: Optional path to trading_requirements.yaml
                (defaults to backend/app/config/trading_requirements.yaml)
        """
        if requirements_path is None:
            base_path = pathlib.Path(__file__).parent.parent.parent
            requirements_path = base_path / "config" / "trading_requirements.yaml"

        self.requirements_path = pathlib.Path(requirements_path)
        self.requirements = self._load_requirements()

    def _load_requirements(self) -> dict[str, Any]:
        """Load trading requirements from YAML config.

        Returns:
            Dict with requirements structure

        Raises:
            FileNotFoundError: If requirements file doesn't exist
            yaml.YAMLError: If YAML parsing fails
        """
        if not self.requirements_path.exists():
            msg = f"Trading requirements file not found: {self.requirements_path}"
            raise FileNotFoundError(msg)

        logger.info(
            "loading_trading_requirements",
            path=str(self.requirements_path),
        )

        with self.requirements_path.open(encoding="utf-8") as f:
            requirements = yaml.safe_load(f)

        logger.info(
            "trading_requirements_loaded",
            version=requirements.get("version"),
            total_gaps=requirements.get("metadata", {}).get("total_gaps"),
            analysis_types=len(requirements.get("analysis_types", {})),
        )

        return requirements  # type: ignore[no-any-return]

    def get_analysis_types(self) -> dict[str, Any]:
        """Get all analysis types configuration."""
        return self.requirements.get("analysis_types", {})  # type: ignore[no-any-return]

    def get_edge_capabilities(self) -> dict[str, Any]:
        """Get edge capabilities configuration."""
        return self.requirements.get("edge_capabilities", {})  # type: ignore[no-any-return]

    def get_mvp_roadmap(self) -> dict[str, Any]:
        """Get MVP roadmap configuration."""
        return self.requirements.get("mvp_roadmap", {})  # type: ignore[no-any-return]
