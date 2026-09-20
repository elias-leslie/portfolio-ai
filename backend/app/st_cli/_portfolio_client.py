"""Resolve and call the Portfolio AI backend for the owner ST command."""

from __future__ import annotations

from pathlib import Path

from st_sdk.project_client import (
    ProjectApi,
    ProjectApiClient,
    ProjectApiConnectError,
    ResolvedURL,
    resolve_api_url,
)

ENV_PORTFOLIO_API_URL = "ST_PORTFOLIO_API_URL"
PORTFOLIO_PROJECT_ID = "portfolio-ai"
DEFAULT_PORTFOLIO_API_URL = "http://localhost:8000"

PORTFOLIO_API = ProjectApi(
    project_id=PORTFOLIO_PROJECT_ID,
    env_var=ENV_PORTFOLIO_API_URL,
    default_url=DEFAULT_PORTFOLIO_API_URL,
)

PortfolioConnectError = ProjectApiConnectError
PortfolioClient = ProjectApiClient


def resolve_portfolio_api_url(*, remote: bool = False, cwd: Path | None = None) -> ResolvedURL:
    return resolve_api_url(PORTFOLIO_API, remote=remote, cwd=cwd)


__all__ = [
    "DEFAULT_PORTFOLIO_API_URL",
    "ENV_PORTFOLIO_API_URL",
    "PORTFOLIO_API",
    "PORTFOLIO_PROJECT_ID",
    "PortfolioClient",
    "PortfolioConnectError",
    "ResolvedURL",
    "resolve_portfolio_api_url",
]

