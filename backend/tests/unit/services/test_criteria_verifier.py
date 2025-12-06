"""Unit tests for CriteriaVerifier service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.criteria_verifier import CriteriaVerifier


@pytest.fixture
def verifier() -> CriteriaVerifier:
    """Create a CriteriaVerifier instance with mocked database."""
    with patch("app.services.criteria_verifier.get_connection_manager"):
        return CriteriaVerifier()


class TestParseHelpers:
    """Test parsing helper methods."""

    def test_parse_curl_command_basic(self, verifier: CriteriaVerifier) -> None:
        """Test parsing basic curl command."""
        url, jq_filter = verifier._parse_curl_command(
            "curl -s http://localhost:8000/api/health"
        )
        assert url == "http://localhost:8000/api/health"
        assert jq_filter is None

    def test_parse_curl_command_with_jq(self, verifier: CriteriaVerifier) -> None:
        """Test parsing curl command with jq filter."""
        url, jq_filter = verifier._parse_curl_command(
            "curl -s http://localhost:8000/api/health | jq '.status'"
        )
        assert url == "http://localhost:8000/api/health"
        assert jq_filter == ".status"

    def test_parse_curl_command_with_object_jq(self, verifier: CriteriaVerifier) -> None:
        """Test parsing curl with object projection jq filter."""
        url, jq_filter = verifier._parse_curl_command(
            "curl -s http://localhost:8000/api/data | jq '{value: .value}'"
        )
        assert url == "http://localhost:8000/api/data"
        assert "{value: .value}" in jq_filter

    def test_parse_curl_command_invalid(self, verifier: CriteriaVerifier) -> None:
        """Test parsing invalid curl command."""
        url, jq_filter = verifier._parse_curl_command("invalid command")
        assert url is None
        assert jq_filter is None

    def test_parse_pytest_command_basic(self, verifier: CriteriaVerifier) -> None:
        """Test parsing basic pytest command."""
        args = verifier._parse_pytest_command("pytest tests/unit/test_example.py")
        assert args == ["tests/unit/test_example.py"]

    def test_parse_pytest_command_with_k_flag(self, verifier: CriteriaVerifier) -> None:
        """Test parsing pytest with -k flag."""
        args = verifier._parse_pytest_command('pytest tests/ -k "test_something"')
        assert "tests/" in args
        assert "-k" in args
        assert "test_something" in args

    def test_parse_pytest_command_no_prefix(self, verifier: CriteriaVerifier) -> None:
        """Test parsing command without pytest prefix."""
        args = verifier._parse_pytest_command("not a pytest command")
        assert args is None

    def test_parse_screenshot_command_basic(self, verifier: CriteriaVerifier) -> None:
        """Test parsing screenshot command."""
        path = verifier._parse_screenshot_command("screenshot /dashboard")
        assert path == "/dashboard"

    def test_parse_screenshot_command_with_description(self, verifier: CriteriaVerifier) -> None:
        """Test parsing screenshot with description."""
        path = verifier._parse_screenshot_command(
            "screenshot /watchlist showing expanded row"
        )
        assert path == "/watchlist"

    def test_parse_screenshot_command_invalid(self, verifier: CriteriaVerifier) -> None:
        """Test parsing invalid screenshot command."""
        path = verifier._parse_screenshot_command("invalid command")
        assert path is None


class TestUrlValidation:
    """Test URL validation."""

    def test_localhost_allowed(self, verifier: CriteriaVerifier) -> None:
        """Test localhost URL is allowed."""
        assert verifier._is_url_allowed("http://localhost:8000/api/test")

    def test_127001_allowed(self, verifier: CriteriaVerifier) -> None:
        """Test 127.0.0.1 URL is allowed."""
        assert verifier._is_url_allowed("http://127.0.0.1:8000/api/test")

    def test_local_network_allowed(self, verifier: CriteriaVerifier) -> None:
        """Test local network URL is allowed."""
        assert verifier._is_url_allowed("http://192.168.8.233:8000/api/test")

    def test_external_not_allowed(self, verifier: CriteriaVerifier) -> None:
        """Test external URL is not allowed."""
        assert not verifier._is_url_allowed("http://example.com/api/test")

    def test_https_external_not_allowed(self, verifier: CriteriaVerifier) -> None:
        """Test HTTPS external URL is not allowed."""
        assert not verifier._is_url_allowed("https://api.example.com/data")


class TestJqFilter:
    """Test jq filter application."""

    def test_simple_field(self, verifier: CriteriaVerifier) -> None:
        """Test simple field extraction."""
        data = {"status": "ok", "value": 42}
        result = verifier._apply_jq_filter(data, ".status")
        assert result == "ok"

    def test_nested_field(self, verifier: CriteriaVerifier) -> None:
        """Test nested field extraction."""
        data = {"outer": {"inner": "value"}}
        result = verifier._apply_jq_filter(data, ".outer.inner")
        assert result == "value"

    def test_object_projection(self, verifier: CriteriaVerifier) -> None:
        """Test object projection."""
        data = {"a": 1, "b": 2, "c": 3}
        result = verifier._apply_jq_filter(data, "{x: .a, y: .b}")
        assert result == {"x": 1, "y": 2}

    def test_identity(self, verifier: CriteriaVerifier) -> None:
        """Test identity filter."""
        data = {"key": "value"}
        result = verifier._apply_jq_filter(data, ".")
        assert result == data

    def test_missing_field(self, verifier: CriteriaVerifier) -> None:
        """Test extraction of missing field."""
        data = {"a": 1}
        result = verifier._apply_jq_filter(data, ".b")
        assert result is None


class TestVerifyApiCriterion:
    """Test API criterion verification."""

    @pytest.mark.asyncio
    async def test_verify_api_success(self, verifier: CriteriaVerifier) -> None:
        """Test successful API verification."""
        criterion = {
            "id": "ac-001",
            "criterion": "API returns health",
            "verification": "curl -s http://localhost:8000/api/health | jq '.status'",
            "type": "api",
        }

        with patch("app.services.criteria_verifier.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "ok"}
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await verifier._verify_api_criterion(criterion)

        assert result["passed"] is True
        assert result["verified_by"] == "auto"
        assert result["verified_at"] is not None

    @pytest.mark.asyncio
    async def test_verify_api_404(self, verifier: CriteriaVerifier) -> None:
        """Test API verification with 404 response."""
        criterion = {
            "id": "ac-001",
            "verification": "curl -s http://localhost:8000/api/nonexistent",
            "type": "api",
        }

        with patch("app.services.criteria_verifier.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_response.text = "Not Found"
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await verifier._verify_api_criterion(criterion)

        assert result["passed"] is False
        assert "404" in result["verification_output"]

    @pytest.mark.asyncio
    async def test_verify_api_url_not_allowed(self, verifier: CriteriaVerifier) -> None:
        """Test API verification with disallowed URL."""
        criterion = {
            "id": "ac-001",
            "verification": "curl -s http://example.com/api/data",
            "type": "api",
        }

        result = await verifier._verify_api_criterion(criterion)

        assert result["passed"] is False
        assert "not allowed" in result["verification_output"]

    @pytest.mark.asyncio
    async def test_verify_api_parse_error(self, verifier: CriteriaVerifier) -> None:
        """Test API verification with unparseable verification string."""
        criterion = {
            "id": "ac-001",
            "verification": "invalid verification string",
            "type": "api",
        }

        result = await verifier._verify_api_criterion(criterion)

        assert result["passed"] is False
        assert "parse" in result["verification_output"].lower() or "url" in result["verification_output"].lower()


class TestVerifyTestCriterion:
    """Test pytest criterion verification."""

    @pytest.mark.asyncio
    async def test_verify_test_success(self, verifier: CriteriaVerifier) -> None:
        """Test successful pytest verification."""
        criterion = {
            "id": "ac-001",
            "verification": "pytest tests/unit/test_example.py",
            "type": "test",
        }

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate.return_value = (b"PASSED", b"")
            mock_exec.return_value = mock_proc

            result = await verifier._verify_test_criterion(criterion)

        assert result["passed"] is True
        assert result["verified_by"] == "pytest"

    @pytest.mark.asyncio
    async def test_verify_test_failure(self, verifier: CriteriaVerifier) -> None:
        """Test failed pytest verification."""
        criterion = {
            "id": "ac-001",
            "verification": "pytest tests/unit/test_failing.py",
            "type": "test",
        }

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.returncode = 1
            mock_proc.communicate.return_value = (b"FAILED", b"AssertionError")
            mock_exec.return_value = mock_proc

            result = await verifier._verify_test_criterion(criterion)

        assert result["passed"] is False

    @pytest.mark.asyncio
    async def test_verify_test_invalid_path(self, verifier: CriteriaVerifier) -> None:
        """Test test verification with invalid path."""
        criterion = {
            "id": "ac-001",
            "verification": "pytest /etc/passwd",
            "type": "test",
        }

        result = await verifier._verify_test_criterion(criterion)

        assert result["passed"] is False
        assert "tests/" in result["verification_output"]


class TestVerifyCriterion:
    """Test main verify_criterion method."""

    @pytest.mark.asyncio
    async def test_dispatch_api(self, verifier: CriteriaVerifier) -> None:
        """Test dispatch to API verification."""
        criterion = {
            "id": "ac-001",
            "verification": "curl -s http://localhost:8000/api/health",
            "type": "api",
        }

        with patch.object(verifier, "_verify_api_criterion", new_callable=AsyncMock) as mock:
            mock.return_value = {"passed": True, "verified_by": "auto"}
            result = await verifier.verify_criterion("FEAT-001", criterion)

        mock.assert_called_once_with(criterion)

    @pytest.mark.asyncio
    async def test_dispatch_test(self, verifier: CriteriaVerifier) -> None:
        """Test dispatch to test verification."""
        criterion = {
            "id": "ac-001",
            "verification": "pytest tests/test_x.py",
            "type": "test",
        }

        with patch.object(verifier, "_verify_test_criterion", new_callable=AsyncMock) as mock:
            mock.return_value = {"passed": True, "verified_by": "pytest"}
            result = await verifier.verify_criterion("FEAT-001", criterion)

        mock.assert_called_once_with(criterion)

    @pytest.mark.asyncio
    async def test_dispatch_ui(self, verifier: CriteriaVerifier) -> None:
        """Test dispatch to UI verification."""
        criterion = {
            "id": "ac-001",
            "verification": "screenshot /dashboard",
            "type": "ui",
        }

        with patch.object(verifier, "_verify_ui_criterion", new_callable=AsyncMock) as mock:
            mock.return_value = {"passed": True, "verified_by": "browser"}
            result = await verifier.verify_criterion("FEAT-001", criterion)

        mock.assert_called_once_with("FEAT-001", criterion)

    @pytest.mark.asyncio
    async def test_manual_type(self, verifier: CriteriaVerifier) -> None:
        """Test handling of manual criterion type."""
        criterion = {
            "id": "ac-001",
            "verification": "check code quality",
            "type": "backend",
            "passed": None,
        }

        result = await verifier.verify_criterion("FEAT-001", criterion)

        assert result["verified_by"] == "manual_required"
        assert "manual" in result["verification_output"].lower()

    @pytest.mark.asyncio
    async def test_unknown_type(self, verifier: CriteriaVerifier) -> None:
        """Test handling of unknown criterion type."""
        criterion = {
            "id": "ac-001",
            "verification": "something",
            "type": "unknown",
        }

        result = await verifier.verify_criterion("FEAT-001", criterion)

        assert result["verified_by"] == "unknown_type"
        assert "unknown" in result["verification_output"].lower()
