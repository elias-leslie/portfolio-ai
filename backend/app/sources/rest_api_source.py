"""Generic REST API source adapter driven by configuration.

Adapted from market-sim for portfolio-ai with the following changes:
- Removed perf_profiler dependency (use time.time() for duration tracking)
- Removed job_queue dependency (use Celery directly)
- Use portfolio-ai's logging_config.get_logger()
- Simplified to focus on core multi-source failover functionality
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import time
from collections.abc import Iterable

import httpx
import polars as pl
from httpx import BasicAuth, HTTPStatusError, Request, Response

from ..logging_config import get_logger
from .base import BaseSource, DatasetRequest
from .jsonpath_mapper import extract_with_path, map_response_to_schema

logger = get_logger(__name__)


class RestApiSource(BaseSource):
    """Dynamic REST API source driven by configuration.

    No hardcoded field mappings or endpoint URLs - everything driven by:
    - source_config: Connection, auth, rate limits
    - endpoints: Path templates, field mappings
    """

    def __init__(
        self,
        source_config: dict[str, object],
        credentials: dict[str, str],
        endpoints: list[dict[str, object]],
    ):
        """Initialize from configuration.

        Args:
            source_config: Source configuration dict with name, priority, definition
            credentials: Source credentials dict
            endpoints: List of endpoint configuration dicts
        """
        # Basic metadata
        self.name = str(source_config.get("source", "unknown"))
        priority_value = source_config.get("priority", 100)
        self.priority = int(priority_value) if isinstance(priority_value, int | str) else 100

        # Parse definition
        definition = source_config.get("definition", {})
        if isinstance(definition, dict):
            self.connection = definition.get("connection", {})
            self.rate_limiting = definition.get("rate_limiting", {})
            self._definition_base_url = definition.get("base_url", "")
        else:
            self.connection = {}
            self.rate_limiting = {}
            self._definition_base_url = ""

        # Index endpoints by key and target table
        self.endpoints = {str(ep["endpoint_key"]): ep for ep in endpoints}
        self.endpoints_by_table: dict[str, list[dict[str, object]]] = {}
        for ep in endpoints:
            target = ep.get("target_table")
            if target:
                if target not in self.endpoints_by_table:
                    self.endpoints_by_table[str(target)] = []
                self.endpoints_by_table[str(target)].append(ep)

        # Set capability flags based on target tables
        self.supports_day = "day_bars" in self.endpoints_by_table
        self.supports_reference = "reference_cache" in self.endpoints_by_table
        self.supports_news = "news_cache" in self.endpoints_by_table

        # Resolve auth credentials
        auth_def: dict[str, object] = {}
        if isinstance(definition, dict):
            temp_auth = definition.get("auth", {})
            if isinstance(temp_auth, dict):
                auth_def = temp_auth
        if not auth_def and isinstance(self.connection, dict):
            temp_auth2 = self.connection.get("auth", {})
            if isinstance(temp_auth2, dict):
                auth_def = temp_auth2
        self.auth_config = self._resolve_auth(auth_def, credentials)

        # Create HTTP client
        self.client = self._create_client()

    def _resolve_auth(
        self, auth_config: dict[str, object], credentials: dict[str, str]
    ) -> dict[str, object]:
        """Replace credential placeholders with actual values.

        Supported formats:
        - {{secret.source/field}} or {{secret:source:field}} (placeholder)
        - {"credential_field": "apiKey"} (direct field reference)
        - {"type": "query", "query_param": "apikey"} (infer from param name)
        """
        resolved: dict[str, object] = dict(auth_config)

        # Method 1: Resolve placeholder in value field
        if "value" in resolved:
            value = resolved["value"]
            if isinstance(value, str) and "{{secret" in value:
                placeholder = value.strip("{}")

                # Handle both dot and colon notation
                if ":" in placeholder:
                    parts = placeholder.split(":")
                    field = parts[2] if len(parts) == 3 else parts[-1]
                else:
                    _, source_field = placeholder.split(".", 1)
                    _, field = source_field.rsplit("/", 1)

                resolved["value"] = credentials.get(field, value)

        # Method 2: Resolve using credential_field
        elif "credential_field" in resolved:
            field = str(resolved["credential_field"])
            if field in credentials:
                resolved["value"] = credentials[field]

        # Method 3: Infer from query_param or key_name
        elif "query_param" in resolved or "key_name" in resolved:
            param_name = str(resolved.get("query_param") or resolved.get("key_name", ""))
            if param_name in credentials:
                resolved["value"] = credentials[param_name]
            else:
                # Try case-insensitive match
                for cred_key, cred_val in credentials.items():
                    if cred_key.lower() == param_name.lower():
                        resolved["value"] = cred_val
                        break

        return resolved

    def _create_client(self) -> httpx.Client:
        """Create HTTP client with base URL and timeout."""
        base_url = ""
        if isinstance(self.connection, dict):
            base_url = str(self.connection.get("base_url", ""))
        if not base_url:
            base_url = self._definition_base_url

        timeout = 30  # Default 30s timeout
        if isinstance(self.connection, dict):
            timeout = int(self.connection.get("timeout", 30))

        return httpx.Client(
            base_url=base_url,
            timeout=timeout,
            follow_redirects=True,
        )

    def _build_request_kwargs(
        self, endpoint: dict[str, object], params: dict[str, str]
    ) -> dict[str, object]:
        """Build httpx request kwargs with authentication."""
        kwargs: dict[str, object] = {
            "method": str(endpoint.get("http_method", "GET")),
        }

        auth_type = self.auth_config.get("type")

        # Query parameter auth
        if auth_type in ("query", "query_param"):
            query_param = str(
                self.auth_config.get("key_name") or self.auth_config.get("query_param") or "apiKey"
            )
            auth_value = self.auth_config.get("value")
            if auth_value:
                params[query_param] = str(auth_value)

        # API key header auth
        elif auth_type == "api_key":
            header = str(self.auth_config.get("header", "Authorization"))
            kwargs["headers"] = {header: str(self.auth_config["value"])}

        # Bearer token auth
        elif auth_type == "bearer":
            token = str(self.auth_config.get("token", ""))
            kwargs["headers"] = {"Authorization": f"Bearer {token}"}

        # Basic auth
        elif auth_type == "basic":
            kwargs["auth"] = BasicAuth(
                str(self.auth_config.get("username", "")),
                str(self.auth_config.get("password", "")),
            )

        kwargs["params"] = params
        return kwargs

    def _call_endpoint(
        self,
        endpoint_key: str,
        path_params: dict[str, str],
        query_params: dict[str, str],
    ) -> dict[str, object]:
        """Call API endpoint with parameters.

        Args:
            endpoint_key: Key from endpoints dict
            path_params: Values for path template placeholders
            query_params: Query string parameters

        Returns:
            Parsed JSON response

        Raises:
            HTTPStatusError: On HTTP errors (4xx, 5xx)
        """
        endpoint = self.endpoints[endpoint_key]

        # Format path template
        path_template = str(endpoint.get("path_template", ""))
        path = path_template.format(**path_params)

        # Build request with auth
        request_kwargs = self._build_request_kwargs(endpoint, query_params)

        # Track duration for performance logging
        start_time = time.time()

        # Execute request
        # httpx.Client.request() has strict typed kwargs but we build them dynamically.
        # dict[str, object] is correct at runtime but mypy can't verify it matches httpx types.
        response = self.client.request(url=path, **request_kwargs)  # type: ignore[arg-type]
        response.raise_for_status()

        duration_ms = int((time.time() - start_time) * 1000)

        logger.info(
            "rest_api_call_success",
            source=self.name,
            endpoint=endpoint_key,
            duration_ms=duration_ms,
            status_code=response.status_code,
        )

        result: dict[str, object] = response.json()
        return result

    def fetch_day_bars(self, request: DatasetRequest) -> pl.DataFrame | None:
        """Fetch daily OHLCV bars."""
        if not self.supports_day:
            return None

        endpoint = self.endpoints_by_table["day_bars"][0]
        endpoint_key = str(endpoint["endpoint_key"])
        frames = []

        logger.info(
            "fetch_day_bars_start",
            source=self.name,
            num_tickers=len(list(request.tickers)),
            date_range=f"{request.start} to {request.end}",
        )

        for ticker in request.tickers:
            try:
                # Build params based on endpoint requirements
                path_params: dict[str, str] = {}
                query_params: dict[str, str] = {}

                # Check for ticker in path template
                path_template = str(endpoint.get("path_template", ""))
                if "{ticker}" in path_template or "{symbol}" in path_template:
                    path_params["ticker"] = ticker
                    path_params["symbol"] = ticker

                # Add date range if path template uses it
                if "{from}" in path_template:
                    path_params["from"] = request.start.isoformat()
                    path_params["to"] = request.end.isoformat()

                # Add symbol to query params if needed
                query_params["symbol"] = ticker

                # Call API
                response = self._call_endpoint(endpoint_key, path_params, query_params)

                # Extract and map data
                mapping_config = {
                    "field_mapping": endpoint.get("field_mapping", {}),
                    "data_path": endpoint.get("response_data_path", "results"),
                }

                df = map_response_to_schema(response, mapping_config)
                if df is None or len(df) == 0:
                    continue

                # Add ticker column if not present
                if "ticker" not in df.columns:
                    df = df.with_columns(pl.lit(ticker).alias("ticker"))

                # Add source lineage
                df = df.with_columns(pl.lit(self.name).alias("source"))

                # Add ingest_run_id if provided
                if request.ingest_run_id:
                    df = df.with_columns(pl.lit(request.ingest_run_id).alias("ingest_run_id"))

                frames.append(df)

                logger.debug(
                    "fetch_day_bars_ticker_success",
                    source=self.name,
                    ticker=ticker,
                    rows=len(df),
                )

            except HTTPStatusError as e:
                logger.warning(
                    "fetch_day_bars_http_error",
                    source=self.name,
                    ticker=ticker,
                    status_code=e.response.status_code,
                    error=str(e),
                )
                # Re-raise to allow multi-source failover
                raise
            except Exception as e:
                logger.warning(
                    "fetch_day_bars_error",
                    source=self.name,
                    ticker=ticker,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                continue

        if not frames:
            return None

        combined = pl.concat(frames, how="vertical_relaxed")
        logger.info(
            "fetch_day_bars_complete",
            source=self.name,
            total_rows=len(combined),
            tickers_fetched=len(frames),
        )

        return combined

    def fetch_reference_payload(
        self, tickers: Iterable[str], as_of: dt.date
    ) -> pl.DataFrame | None:
        """Fetch reference data (company info, sector, etc.)."""
        if not self.supports_reference:
            return None

        endpoint = self.endpoints_by_table["reference_cache"][0]
        endpoint_key = str(endpoint["endpoint_key"])
        records = []

        for ticker in tickers:
            try:
                path_params: dict[str, str] = {}
                query_params: dict[str, str] = {}

                # Check path template for ticker placeholder
                path_template = str(endpoint.get("path_template", ""))
                if "{ticker}" in path_template:
                    path_params["ticker"] = ticker
                elif "{symbol}" in path_template:
                    path_params["symbol"] = ticker

                # Add to query params if needed
                query_params["symbol"] = ticker
                query_params["ticker"] = ticker

                # Call API
                response = self._call_endpoint(endpoint_key, path_params, query_params)

                # Check for error codes in response
                if isinstance(response, dict) and "code" in response:
                    status_code = response.get("code")
                    if isinstance(status_code, int) and status_code in (401, 403, 429):
                        fake_request = Request("GET", "")
                        fake_response = Response(status_code, request=fake_request)
                        raise HTTPStatusError(
                            str(response.get("message", f"API error {status_code}")),
                            request=fake_request,
                            response=fake_response,
                        )

                # Extract data
                data_path = endpoint.get("response_data_path", "")
                if data_path:
                    payload = extract_with_path(response, str(data_path))
                else:
                    payload = response

                if not payload:
                    continue

                # Apply field mapping if present
                field_mapping_obj = endpoint.get("field_mapping", {})
                if (
                    field_mapping_obj
                    and isinstance(payload, dict)
                    and isinstance(field_mapping_obj, dict)
                ):
                    mapped_payload = {}
                    for target_field, source_field in field_mapping_obj.items():
                        if "." in str(source_field):
                            value = extract_with_path(payload, str(source_field))
                        else:
                            value = payload.get(str(source_field))
                        mapped_payload[str(target_field)] = value
                    payload = mapped_payload

                # Convert to JSON string for storage
                payload_json = json.dumps(payload) if not isinstance(payload, str) else payload

                records.append(
                    {
                        "ticker": ticker,
                        "as_of_date": as_of,
                        "payload": payload_json,
                        "source": self.name,
                    }
                )

            except HTTPStatusError:
                raise  # Re-raise for failover
            except Exception as e:
                logger.warning(
                    "fetch_reference_error",
                    source=self.name,
                    ticker=ticker,
                    error=str(e),
                )
                continue

        if not records:
            return None

        return pl.DataFrame(records)

    def fetch_news_payload(
        self, tickers: Iterable[str], start: dt.datetime, end: dt.datetime
    ) -> pl.DataFrame | None:
        """Fetch news articles."""
        if not self.supports_news:
            return None

        endpoint = self.endpoints_by_table["news_cache"][0]
        endpoint_key = str(endpoint["endpoint_key"])
        records = []

        for ticker in tickers:
            try:
                query_params: dict[str, str] = {"q": ticker}

                # Add date range if supported
                if start:
                    query_params["from"] = start.date().isoformat()
                if end:
                    query_params["to"] = end.date().isoformat()

                # Call API
                response = self._call_endpoint(endpoint_key, {}, query_params)

                # Extract articles
                data_path = str(endpoint.get("response_data_path", "articles"))
                articles = extract_with_path(response, data_path)

                if not articles or not isinstance(articles, list):
                    continue

                # Map article fields
                field_mapping_obj = endpoint.get("field_mapping", {})
                article_records = []

                if not isinstance(field_mapping_obj, dict):
                    continue

                for article in articles:
                    if not isinstance(article, dict):
                        continue

                    record: dict[str, object] = {}
                    for target_field, source_field in field_mapping_obj.items():
                        if "." in str(source_field):
                            value = extract_with_path(article, str(source_field))
                        else:
                            value = article.get(str(source_field))
                        record[str(target_field)] = value

                    if not record.get("headline") or not record.get("url"):
                        continue

                    article_records.append(record)

                if not article_records:
                    continue

                # Determine publication date
                pub_date = dt.date.today()
                if article_records:
                    first_article = article_records[0]
                    pub_date_str = first_article.get("published_at")
                    if pub_date_str and isinstance(pub_date_str, str):
                        with contextlib.suppress(Exception):
                            pub_date = dt.datetime.fromisoformat(
                                pub_date_str.replace("Z", "+00:00")
                            ).date()

                records.append(
                    {
                        "ticker": ticker,
                        "date_utc": pub_date,
                        "payload": article_records,
                        "source": self.name,
                    }
                )

            except Exception as e:
                logger.warning(
                    "fetch_news_error",
                    source=self.name,
                    ticker=ticker,
                    error=str(e),
                )
                continue

        if not records:
            return None

        return pl.DataFrame(records)

    def __del__(self) -> None:
        """Close HTTP client on cleanup."""
        if hasattr(self, "client"):
            self.client.close()
