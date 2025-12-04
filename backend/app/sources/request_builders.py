"""HTTP request builders for REST API sources.

Handles request construction, authentication, and parameter formatting.
"""

from __future__ import annotations

import datetime as dt

from httpx import BasicAuth


def build_request_kwargs(
    endpoint: dict[str, object], auth_config: dict[str, object], params: dict[str, str]
) -> dict[str, object]:
    """Build httpx request kwargs with authentication.

    Args:
        endpoint: Endpoint configuration with http_method, etc.
        auth_config: Resolved authentication configuration
        params: Query parameters (will be modified for query auth)

    Returns:
        Dict of kwargs to pass to httpx.Client.request()
    """
    kwargs: dict[str, object] = {
        "method": str(endpoint.get("http_method", "GET")),
    }

    auth_type = auth_config.get("type")

    # Query parameter auth
    if auth_type in ("query", "query_param"):
        query_param = str(auth_config.get("key_name") or auth_config.get("query_param") or "apiKey")
        auth_value = auth_config.get("value")
        if auth_value:
            params[query_param] = str(auth_value)

    # API key header auth
    elif auth_type == "api_key":
        header = str(auth_config.get("header", "Authorization"))
        kwargs["headers"] = {header: str(auth_config["value"])}

    # Bearer token auth
    elif auth_type == "bearer":
        token = str(auth_config.get("token", ""))
        kwargs["headers"] = {"Authorization": f"Bearer {token}"}

    # Basic auth
    elif auth_type == "basic":
        kwargs["auth"] = BasicAuth(
            str(auth_config.get("username", "")),
            str(auth_config.get("password", "")),
        )

    kwargs["params"] = params
    return kwargs


def build_symbol_params(
    symbol: str,
    endpoint: dict[str, object],
    date_range: tuple[dt.date, dt.date] | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    """Build path and query params for a symbol request.

    Args:
        symbol: Stock symbol
        endpoint: Endpoint configuration dictionary
        date_range: Optional (start_date, end_date) tuple

    Returns:
        Tuple of (path_params, query_params)
    """
    path_params: dict[str, str] = {}
    query_params: dict[str, str] = {}

    # Check for symbol in path template
    path_template = str(endpoint.get("path_template", ""))
    if "{ticker}" in path_template or "{symbol}" in path_template:
        path_params["ticker"] = symbol
        path_params["symbol"] = symbol

    # Add date range if path template uses it
    if date_range and "{from}" in path_template:
        path_params["from"] = date_range[0].isoformat()
        path_params["to"] = date_range[1].isoformat()

    # Add symbol to query params
    query_params["ticker"] = symbol
    query_params["symbol"] = symbol

    return path_params, query_params
