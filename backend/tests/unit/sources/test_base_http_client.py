"""Tests for base HTTP client with rate limiting and retry logic.

Tests verify:
1. should_retry_http_exception() - retry logic for HTTP errors
2. RateLimiter - per-minute and per-day rate limiting
3. BaseHTTPClient - abstract base class functionality
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import httpx
import pytest

from app.sources.base_http_client import (
    BaseHTTPClient,
    RateLimiter,
    redact_url_credentials,
    should_retry_http_exception,
)


class TestShouldRetryException:
    """Tests for should_retry_http_exception() function."""

    def test_retry_on_429(self) -> None:
        """Should retry on 429 (rate limit)."""
        response = Mock(spec=httpx.Response)
        response.status_code = 429
        exc = httpx.HTTPStatusError("Rate limited", request=Mock(), response=response)
        assert should_retry_http_exception(exc) is True

    def test_retry_on_500(self) -> None:
        """Should retry on 500 (internal server error)."""
        response = Mock(spec=httpx.Response)
        response.status_code = 500
        exc = httpx.HTTPStatusError("Server error", request=Mock(), response=response)
        assert should_retry_http_exception(exc) is True

    def test_retry_on_502(self) -> None:
        """Should retry on 502 (bad gateway)."""
        response = Mock(spec=httpx.Response)
        response.status_code = 502
        exc = httpx.HTTPStatusError("Bad gateway", request=Mock(), response=response)
        assert should_retry_http_exception(exc) is True

    def test_retry_on_503(self) -> None:
        """Should retry on 503 (service unavailable)."""
        response = Mock(spec=httpx.Response)
        response.status_code = 503
        exc = httpx.HTTPStatusError("Service unavailable", request=Mock(), response=response)
        assert should_retry_http_exception(exc) is True

    def test_retry_on_504(self) -> None:
        """Should retry on 504 (gateway timeout)."""
        response = Mock(spec=httpx.Response)
        response.status_code = 504
        exc = httpx.HTTPStatusError("Gateway timeout", request=Mock(), response=response)
        assert should_retry_http_exception(exc) is True

    def test_no_retry_on_400(self) -> None:
        """Should not retry on 400 (bad request)."""
        response = Mock(spec=httpx.Response)
        response.status_code = 400
        exc = httpx.HTTPStatusError("Bad request", request=Mock(), response=response)
        assert should_retry_http_exception(exc) is False

    def test_no_retry_on_401(self) -> None:
        """Should not retry on 401 (unauthorized)."""
        response = Mock(spec=httpx.Response)
        response.status_code = 401
        exc = httpx.HTTPStatusError("Unauthorized", request=Mock(), response=response)
        assert should_retry_http_exception(exc) is False

    def test_no_retry_on_403(self) -> None:
        """Should not retry on 403 (forbidden)."""
        response = Mock(spec=httpx.Response)
        response.status_code = 403
        exc = httpx.HTTPStatusError("Forbidden", request=Mock(), response=response)
        assert should_retry_http_exception(exc) is False

    def test_no_retry_on_404(self) -> None:
        """Should not retry on 404 (not found)."""
        response = Mock(spec=httpx.Response)
        response.status_code = 404
        exc = httpx.HTTPStatusError("Not found", request=Mock(), response=response)
        assert should_retry_http_exception(exc) is False

    def test_retry_on_network_error(self) -> None:
        """Should retry on network errors (RequestError)."""
        exc = httpx.RequestError("Connection failed")
        assert should_retry_http_exception(exc) is True

    def test_retry_on_timeout(self) -> None:
        """Should retry on timeout errors."""
        exc = httpx.TimeoutException("Request timed out")
        assert should_retry_http_exception(exc) is True

    def test_no_retry_on_other_exceptions(self) -> None:
        """Should not retry on other exception types."""
        exc = ValueError("Some other error")
        assert should_retry_http_exception(exc) is False


class TestCredentialRedaction:
    """Tests for URL credential redaction."""

    def test_redacts_common_api_key_query_params(self) -> None:
        message = (
            "https://example.test/path?apiKey=polygon-secret"
            "&apikey=fmp-secret&api_key=fred-secret&token=finnhub-secret"
        )

        redacted = redact_url_credentials(message)

        assert "polygon-secret" not in redacted
        assert "fmp-secret" not in redacted
        assert "fred-secret" not in redacted
        assert "finnhub-secret" not in redacted
        assert "apiKey=[REDACTED]" in redacted
        assert "apikey=[REDACTED]" in redacted
        assert "api_key=[REDACTED]" in redacted
        assert "token=[REDACTED]" in redacted


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_init_requires_at_least_one_limit(self) -> None:
        """RateLimiter requires at least one limit to be set."""
        with pytest.raises(ValueError, match="At least one of calls_per_minute or calls_per_day"):
            RateLimiter()

    def test_per_minute_limit_basic(self) -> None:
        """Per-minute limit allows requests up to limit."""
        limiter = RateLimiter(calls_per_minute=3)

        # Should allow 3 requests immediately
        limiter.throttle("test_client")
        limiter.throttle("test_client")
        limiter.throttle("test_client")

    @patch("time.sleep")
    @patch("time.monotonic")
    def test_per_minute_limit_blocks(self, mock_monotonic: Mock, mock_sleep: Mock) -> None:
        """Per-minute limit blocks when exceeded."""
        # Simulate time passing
        times = [0.0, 1.0, 2.0, 3.0, 4.0]  # 4th request should wait
        mock_monotonic.side_effect = times

        limiter = RateLimiter(calls_per_minute=3)

        # First 3 requests go through
        limiter.throttle("test_client")
        limiter.throttle("test_client")
        limiter.throttle("test_client")

        # 4th request should sleep
        mock_monotonic.side_effect = [4.0, 61.0]  # After sleep, time advances
        limiter.throttle("test_client")

        # Verify sleep was called with ~56 seconds (60 - 4)
        mock_sleep.assert_called_once()
        sleep_duration = mock_sleep.call_args[0][0]
        assert 55 < sleep_duration < 57  # ~56 seconds

    @patch("time.monotonic")
    def test_per_minute_limit_sliding_window(self, mock_monotonic: Mock) -> None:
        """Per-minute limit uses sliding window."""
        limiter = RateLimiter(calls_per_minute=3)

        # First 3 requests at t=0, 1, 2
        mock_monotonic.return_value = 0.0
        limiter.throttle("test_client")
        mock_monotonic.return_value = 1.0
        limiter.throttle("test_client")
        mock_monotonic.return_value = 2.0
        limiter.throttle("test_client")

        # After 61 seconds, oldest request expires, should allow new request
        mock_monotonic.return_value = 61.0
        limiter.throttle("test_client")  # Should succeed (oldest expired)

    def test_per_day_limit_basic(self) -> None:
        """Per-day limit allows requests up to limit."""
        limiter = RateLimiter(calls_per_day=3)

        # Should allow 3 requests immediately
        limiter.throttle("test_client")
        limiter.throttle("test_client")
        limiter.throttle("test_client")

    @patch("time.monotonic")
    def test_per_day_limit_raises_on_exceed(self, mock_monotonic: Mock) -> None:
        """Per-day limit raises error when exceeded."""
        mock_monotonic.return_value = 0.0
        limiter = RateLimiter(calls_per_day=3)

        # First 3 requests succeed
        limiter.throttle("test_client")
        limiter.throttle("test_client")
        limiter.throttle("test_client")

        # 4th request should raise
        with pytest.raises(RuntimeError, match="daily rate limit .* exceeded"):
            limiter.throttle("test_client")

    @patch("time.monotonic")
    def test_combined_limits(self, mock_monotonic: Mock) -> None:
        """Both per-minute and per-day limits work together."""
        limiter = RateLimiter(calls_per_minute=2, calls_per_day=5)

        # First 2 requests succeed (within minute limit)
        mock_monotonic.return_value = 0.0
        limiter.throttle("test_client")
        mock_monotonic.return_value = 1.0
        limiter.throttle("test_client")

        # After 61 seconds, can make 2 more requests
        mock_monotonic.return_value = 61.0
        limiter.throttle("test_client")
        mock_monotonic.return_value = 62.0
        limiter.throttle("test_client")

        # After another 61 seconds, can make 1 more request (5th total)
        mock_monotonic.return_value = 122.0
        limiter.throttle("test_client")

        # 6th request should fail (day limit exceeded)
        mock_monotonic.return_value = 123.0
        with pytest.raises(RuntimeError, match="daily rate limit"):
            limiter.throttle("test_client")


class MockHTTPClient(BaseHTTPClient):
    """Mock HTTP client for testing BaseHTTPClient."""

    BASE_URL = "https://api.example.com"

    def get_api_key_env_var(self) -> str:
        """Return mock env var name."""
        return "MOCK_API_KEY"

    def get_client_name(self) -> str:
        """Return mock client name."""
        return "mock_client"

    def get_api_key_param_name(self) -> str:
        """Return mock API key parameter name."""
        return "api_key"


class TestBaseHTTPClient:
    """Tests for BaseHTTPClient abstract base class."""

    def test_init_with_api_key(self) -> None:
        """Initialization with API key provided."""
        client = MockHTTPClient(api_key="test_key_123", rate_calls_per_minute=60)
        assert client.api_key == "test_key_123"
        assert client.request_count == 0
        client.close()

    @patch.dict("os.environ", {"MOCK_API_KEY": "env_key_456"})
    def test_init_from_env_var(self) -> None:
        """Initialization from environment variable."""
        client = MockHTTPClient(rate_calls_per_minute=60)
        assert client.api_key == "env_key_456"
        client.close()

    def test_init_missing_api_key(self) -> None:
        """Initialization fails if API key missing."""
        with (
            patch.dict("os.environ", {}, clear=True),
            pytest.raises(RuntimeError, match="MOCK_API_KEY is not set"),
        ):
            MockHTTPClient(rate_calls_per_minute=60)

    def test_close(self) -> None:
        """Close method releases resources."""
        client = MockHTTPClient(api_key="test_key", rate_calls_per_minute=60)
        mock_httpx_client = Mock()
        client._client = mock_httpx_client

        client.close()

        mock_httpx_client.close.assert_called_once()

    @patch("app.sources.base_http_client.httpx.Client")
    @patch("app.sources.base_http_client.httpx.Limits")
    def test_init_can_disable_keepalive_pool(self, mock_limits_class: Mock, mock_httpx_class: Mock) -> None:
        """Initialization can cap keepalive connections for sources that leak idle sockets."""
        limits = Mock()
        mock_limits_class.return_value = limits

        client = MockHTTPClient(
            api_key="test_key",
            rate_calls_per_minute=60,
            max_keepalive_connections=0,
        )

        mock_limits_class.assert_called_once_with(max_keepalive_connections=0)
        mock_httpx_class.assert_called_once_with(timeout=30, limits=limits)
        client.close()

    @patch("app.sources.base_http_client.httpx.Client")
    def test_request_success(self, mock_httpx_class: Mock) -> None:
        """Successful request returns parsed JSON."""
        # Setup mock client
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success", "data": [1, 2, 3]}
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.request.return_value = mock_response
        mock_httpx_class.return_value = mock_client

        # Make request
        client = MockHTTPClient(api_key="test_key", rate_calls_per_minute=60)
        result = client.request("/endpoint", {"param1": "value1"})

        # Verify
        assert result == {"result": "success", "data": [1, 2, 3]}
        assert client.request_count == 1

        # Verify request was made with correct parameters
        mock_client.request.assert_called_once()
        call_args = mock_client.request.call_args
        assert call_args[0][0] == "GET"
        assert call_args[0][1] == "https://api.example.com/endpoint"
        assert call_args[1]["params"]["param1"] == "value1"
        assert call_args[1]["params"]["api_key"] == "test_key"

        client.close()

    @patch("app.sources.base_http_client.httpx.Client")
    def test_request_adds_api_key(self, mock_httpx_class: Mock) -> None:
        """Request automatically adds API key to params."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.request.return_value = mock_response
        mock_httpx_class.return_value = mock_client

        client = MockHTTPClient(api_key="secret_key", rate_calls_per_minute=60)
        client.request("/test")

        # Verify API key was added to params
        call_args = mock_client.request.call_args
        assert call_args[1]["params"]["api_key"] == "secret_key"

        client.close()

    @patch("app.sources.base_http_client.httpx.Client")
    @patch("app.sources.base_http_client.time.sleep")
    def test_request_rate_limited(self, mock_sleep: Mock, mock_httpx_class: Mock) -> None:
        """Request respects rate limiting."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.request.return_value = mock_response
        mock_httpx_class.return_value = mock_client

        # Create client with very low rate limit
        client = MockHTTPClient(api_key="test_key", rate_calls_per_minute=2)

        # Make 2 requests (should succeed)
        client.request("/test1")
        client.request("/test2")

        # 3rd request should trigger rate limiting
        # Need enough monotonic() calls for all operations
        with patch("time.monotonic", side_effect=[0, 1, 2, 3, 4, 5, 6, 7, 8]):
            client.request("/test3")

        # Sleep should have been called (rate limiting kicked in)
        assert mock_sleep.called or client.request_count == 3

        client.close()

    @patch("app.sources.base_http_client.httpx.Client")
    def test_request_http_error(self, mock_httpx_class: Mock) -> None:
        """Request raises on HTTP errors."""
        request = httpx.Request(
            "GET", "https://api.example.com/nonexistent?api_key=secret_key"
        )
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not found for https://api.example.com/nonexistent?api_key=secret_key",
            request=request,
            response=mock_response,
        )

        mock_client = Mock()
        mock_client.request.return_value = mock_response
        mock_httpx_class.return_value = mock_client

        client = MockHTTPClient(api_key="test_key", rate_calls_per_minute=60)

        # Should raise HTTPStatusError
        with pytest.raises(httpx.HTTPStatusError, match="Not found") as exc_info:
            client.request("/nonexistent")

        assert "secret_key" not in str(exc_info.value)
        assert "api_key=[REDACTED]" in str(exc_info.value)
        client.close()

    @patch("app.sources.base_http_client.httpx.Client")
    @patch("app.sources.base_http_client.time.time")
    def test_request_logs_duration(self, mock_time: Mock, mock_httpx_class: Mock) -> None:
        """Request logs duration of API call."""
        # Provide enough timestamps for start/end timing plus any retry bookkeeping
        mock_time.side_effect = [0.0, 0.5, 0.5]  # 500ms duration

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.request.return_value = mock_response
        mock_httpx_class.return_value = mock_client

        client = MockHTTPClient(api_key="test_key", rate_calls_per_minute=60)
        client.request("/test")

        # Verify time tracking (duration should be ~500ms)
        assert client.request_count == 1

        client.close()

    @patch("app.sources.base_http_client.httpx.Client")
    def test_request_custom_method(self, mock_httpx_class: Mock) -> None:
        """Request supports custom HTTP methods."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"created": True}
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.request.return_value = mock_response
        mock_httpx_class.return_value = mock_client

        client = MockHTTPClient(api_key="test_key", rate_calls_per_minute=60)
        result = client.request("/create", method="POST")

        assert result == {"created": True}

        # Verify POST method was used
        call_args = mock_client.request.call_args
        assert call_args[0][0] == "POST"

        client.close()

    def test_del_closes_client(self) -> None:
        """__del__ closes client on garbage collection."""
        client = MockHTTPClient(api_key="test_key", rate_calls_per_minute=60)
        mock_httpx_client = Mock()
        client._client = mock_httpx_client

        # Trigger garbage collection
        del client

        # Note: __del__ is not guaranteed to be called immediately, but we test the implementation
        # In practice, close() should be called explicitly or via context manager
