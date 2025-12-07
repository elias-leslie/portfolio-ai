"""Criteria Verifier - Auto-verification engine for acceptance criteria.

This module provides automatic verification of acceptance criteria by:
- Executing API criteria (curl commands with jq filters)
- Running test criteria (pytest commands)
- Taking screenshots for UI criteria (browser automation)
- Marking manual criteria as requiring human verification

Usage:
    verifier = CriteriaVerifier()
    result = await verifier.verify_criterion("FEAT-001", criterion_dict)
    results = await verifier.verify_feature("FEAT-001")
    summary = await verifier.verify_all_automatable()
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from ..logging_config import get_logger
from ..storage.connection import get_connection_manager
from . import artifact_manager

logger = get_logger(__name__)

# Safety configuration
ALLOWED_URL_PATTERNS = [
    r"^http://localhost:\d+/api/",
    r"^http://127\.0\.0\.1:\d+/api/",
    r"^http://192\.168\.\d+\.\d+:\d+/",  # Local network
]

MAX_API_TIMEOUT = 10  # seconds
MAX_TEST_TIMEOUT = 60  # seconds
MAX_UI_TIMEOUT = 30  # seconds
MAX_CONCURRENT = 10  # parallel verifications
MAX_OUTPUT_LENGTH = 1000  # truncate output to this length

# Paths
BACKEND_DIR = Path("/home/kasadis/portfolio-ai/backend")
BROWSER_SCRIPTS = Path("/home/kasadis/portfolio-ai/.claude/skills/browser-automation/scripts")

# Auto-verifiable types
AUTO_VERIFIABLE_TYPES = {"api", "test", "ui"}
MANUAL_ONLY_TYPES = {"backend", "quality", "db", "content"}


class CriteriaVerifier:
    """Auto-verification engine for acceptance criteria."""

    def __init__(self) -> None:
        """Initialize the verifier."""
        self.conn_mgr = get_connection_manager()

    async def verify_criterion(
        self, feature_id: str, criterion: dict[str, Any]
    ) -> dict[str, Any]:
        """Verify a single criterion based on its type.

        Args:
            feature_id: The feature ID (e.g., FEAT-001)
            criterion: The criterion dict with id, criterion, verification, type, passed

        Returns:
            Updated criterion dict with passed, verified_at, verified_by, verification_output
        """
        criterion_type = criterion.get("type", "").lower()
        criterion_id = criterion.get("id", "unknown")

        start_time = time.time()
        logger.info(
            "verifying_criterion",
            feature_id=feature_id,
            criterion_id=criterion_id,
            type=criterion_type,
        )

        try:
            if criterion_type == "api":
                result = await self._verify_api_criterion(criterion)
            elif criterion_type == "test":
                result = await self._verify_test_criterion(criterion)
            elif criterion_type == "ui":
                result = await self._verify_ui_criterion(feature_id, criterion)
            elif criterion_type in MANUAL_ONLY_TYPES:
                result = self._handle_manual_criterion(criterion)
            else:
                result = {
                    **criterion,
                    "passed": None,
                    "verified_by": "unknown_type",
                    "verification_output": f"Unknown criterion type: {criterion_type}",
                }

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "criterion_verified",
                feature_id=feature_id,
                criterion_id=criterion_id,
                type=criterion_type,
                passed=result.get("passed"),
                duration_ms=duration_ms,
            )

            return result

        except Exception as e:
            logger.error(
                "criterion_verification_failed",
                feature_id=feature_id,
                criterion_id=criterion_id,
                error=str(e),
            )
            return {
                **criterion,
                "passed": False,
                "verified_at": datetime.now(UTC).isoformat(),
                "verified_by": "error",
                "verification_output": f"Error: {str(e)[:MAX_OUTPUT_LENGTH]}",
            }

    async def verify_feature(self, feature_id: str) -> list[dict[str, Any]]:
        """Verify all criteria for a feature.

        Args:
            feature_id: The feature ID (e.g., FEAT-001)

        Returns:
            List of updated criterion dicts
        """
        # Get feature with criteria
        with self.conn_mgr.connection() as conn:
            row = conn.execute(
                """
                SELECT acceptance_criteria
                FROM feature_capabilities
                WHERE feature_id = %s
                """,
                (feature_id,),
            ).fetchone()

            if not row or not row[0]:
                logger.warning("no_criteria_found", feature_id=feature_id)
                return []

            criteria = row[0]

        # Verify each criterion
        results = []
        for criterion in criteria:
            result = await self.verify_criterion(feature_id, criterion)
            results.append(result)

            # Save result immediately
            await self._save_criterion_result(feature_id, result)

        return results

    async def verify_all_automatable(
        self, type_filter: str | None = None, limit: int | None = None
    ) -> dict[str, Any]:
        """Verify all auto-verifiable criteria across all features.

        Args:
            type_filter: Optional type filter (api, test, ui)
            limit: Optional limit on number of criteria to verify

        Returns:
            Summary dict with counts and timing
        """
        start_time = time.time()

        # Get all features with criteria
        with self.conn_mgr.connection() as conn:
            rows = conn.execute(
                """
                SELECT feature_id, acceptance_criteria
                FROM feature_capabilities
                WHERE acceptance_criteria IS NOT NULL
                  AND jsonb_array_length(acceptance_criteria) > 0
                ORDER BY feature_id
                """
            ).fetchall()

        # Collect all criteria to verify
        to_verify: list[tuple[str, dict]] = []
        for feature_id, criteria in rows:
            for criterion in criteria:
                ctype = criterion.get("type", "").lower()
                if ctype not in AUTO_VERIFIABLE_TYPES:
                    continue
                if type_filter and ctype != type_filter:
                    continue
                to_verify.append((feature_id, criterion))

        if limit:
            to_verify = to_verify[:limit]

        logger.info(
            "starting_bulk_verification",
            total_criteria=len(to_verify),
            type_filter=type_filter,
        )

        # Verify with concurrency limit
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        results = {"passed": 0, "failed": 0, "errors": 0}

        async def verify_with_semaphore(feature_id: str, criterion: dict) -> None:
            async with semaphore:
                result = await self.verify_criterion(feature_id, criterion)
                await self._save_criterion_result(feature_id, result)

                if result.get("passed") is True:
                    results["passed"] += 1
                elif result.get("passed") is False:
                    results["failed"] += 1
                else:
                    results["errors"] += 1

        # Run all verifications
        tasks = [verify_with_semaphore(fid, c) for fid, c in to_verify]
        await asyncio.gather(*tasks, return_exceptions=True)

        duration = time.time() - start_time
        summary = {
            "total_verified": len(to_verify),
            "passed": results["passed"],
            "failed": results["failed"],
            "errors": results["errors"],
            "duration_seconds": round(duration, 2),
            "type_filter": type_filter,
        }

        logger.info("bulk_verification_complete", **summary)
        return summary

    async def _verify_api_criterion(self, criterion: dict) -> dict[str, Any]:
        """Verify an API criterion by making HTTP request.

        Parses curl commands like:
            curl -s http://localhost:8000/api/health | jq '.status'
            curl -s -X POST http://localhost:8000/api/data -d '{"key": "value"}'
            curl -s http://localhost:8000/api/market/fear-greed | jq '.tables | length'

        Automatically resolves placeholders like {id}, {run_id}, {symbol} before
        making the request.
        """
        verification = criterion.get("verification", "")

        # Resolve any placeholders in the verification command
        verification = await self._resolve_api_placeholders(verification)

        # Parse the curl command (method, url, data, jq_filter)
        parsed = self._parse_curl_command_full(verification)

        if not parsed or not parsed.get("url"):
            return {
                **criterion,
                "passed": False,
                "verified_at": datetime.now(UTC).isoformat(),
                "verified_by": "auto",
                "verification_output": f"Could not parse URL from: {verification}",
            }

        url = parsed["url"]
        method = parsed.get("method", "GET").upper()
        data = parsed.get("data")
        jq_filter = parsed.get("jq_filter")

        # Validate URL is allowed
        if not self._is_url_allowed(url):
            return {
                **criterion,
                "passed": False,
                "verified_at": datetime.now(UTC).isoformat(),
                "verified_by": "auto",
                "verification_output": f"URL not allowed: {url}",
            }

        try:
            async with httpx.AsyncClient(timeout=MAX_API_TIMEOUT) as client:
                # Support different HTTP methods
                if method == "POST":
                    response = await client.post(url, json=data if data else None)
                elif method == "PATCH":
                    response = await client.patch(url, json=data if data else None)
                elif method == "PUT":
                    response = await client.put(url, json=data if data else None)
                elif method == "DELETE":
                    response = await client.delete(url)
                else:
                    response = await client.get(url)

            # Check HTTP status (allow 200, 201, 204)
            if response.status_code not in (200, 201, 204):
                return {
                    **criterion,
                    "passed": False,
                    "verified_at": datetime.now(UTC).isoformat(),
                    "verified_by": "auto",
                    "verification_output": f"HTTP {response.status_code}: {response.text[:200]}",
                }

            # Get response data
            try:
                response_data = response.json() if response.text else {}
            except json.JSONDecodeError:
                response_data = response.text[:MAX_OUTPUT_LENGTH]

            # Apply jq filter using real jq CLI if filter exists
            if jq_filter and isinstance(response_data, (dict, list)):
                output = await self._apply_jq_cli(response_data, jq_filter)
            else:
                output = response_data

            # Determine pass/fail - passed if we got success status and some data
            # For filters that return numbers, 0 is falsy but valid
            passed = output is not None and output not in ("", [])

            return {
                **criterion,
                "passed": passed,
                "verified_at": datetime.now(UTC).isoformat(),
                "verified_by": "auto",
                "verification_output": str(output)[:MAX_OUTPUT_LENGTH],
            }

        except httpx.TimeoutException:
            return {
                **criterion,
                "passed": False,
                "verified_at": datetime.now(UTC).isoformat(),
                "verified_by": "auto",
                "verification_output": f"Timeout after {MAX_API_TIMEOUT}s",
            }
        except Exception as e:
            return {
                **criterion,
                "passed": False,
                "verified_at": datetime.now(UTC).isoformat(),
                "verified_by": "auto",
                "verification_output": f"Error: {str(e)[:MAX_OUTPUT_LENGTH]}",
            }

    async def _verify_test_criterion(self, criterion: dict) -> dict[str, Any]:
        """Verify a test criterion by running pytest.

        Parses commands like:
            pytest tests/agents/test_rules_validator.py
            pytest tests/ -k "test_watchlist"
        """
        verification = criterion.get("verification", "")

        # Parse pytest command
        test_args = self._parse_pytest_command(verification)

        if not test_args:
            return {
                **criterion,
                "passed": False,
                "verified_at": datetime.now(UTC).isoformat(),
                "verified_by": "pytest",
                "verification_output": f"Could not parse pytest command: {verification}",
            }

        # Validate test path is under tests/
        test_path = test_args[0] if test_args else ""
        if not test_path.startswith("tests/"):
            return {
                **criterion,
                "passed": False,
                "verified_at": datetime.now(UTC).isoformat(),
                "verified_by": "pytest",
                "verification_output": f"Test path must be under tests/: {test_path}",
            }

        try:
            # Run pytest
            proc = await asyncio.create_subprocess_exec(
                str(BACKEND_DIR / ".venv/bin/pytest"),
                *test_args,
                "-v",
                "--tb=short",
                cwd=str(BACKEND_DIR),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, _stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=MAX_TEST_TIMEOUT
                )
            except TimeoutError:
                proc.kill()
                return {
                    **criterion,
                    "passed": False,
                    "verified_at": datetime.now(UTC).isoformat(),
                    "verified_by": "pytest",
                    "verification_output": f"Timeout after {MAX_TEST_TIMEOUT}s",
                }

            passed = proc.returncode == 0
            output = stdout.decode()[-MAX_OUTPUT_LENGTH:]

            return {
                **criterion,
                "passed": passed,
                "verified_at": datetime.now(UTC).isoformat(),
                "verified_by": "pytest",
                "verification_output": output,
            }

        except Exception as e:
            return {
                **criterion,
                "passed": False,
                "verified_at": datetime.now(UTC).isoformat(),
                "verified_by": "pytest",
                "verification_output": f"Error: {str(e)[:MAX_OUTPUT_LENGTH]}",
            }

    async def _verify_ui_criterion(
        self, feature_id: str, criterion: dict
    ) -> dict[str, Any]:
        """Capture evidence for UI criterion and queue for visual verification.

        Uses capture-evidence.js to:
            1. Take full-page screenshot
            2. Capture console errors/warnings
            3. Track network failures
            4. Measure page state (element counts, text sample)
            5. Record performance metrics

        The AI must then visually inspect the evidence and mark passed/failed.

        Parses commands like:
            screenshot /dashboard and verify gauge visible
            screenshot /watchlist showing expanded row
        """
        verification = criterion.get("verification", "")
        criterion_id = criterion.get("id", "unknown")

        # Parse screenshot command
        url_path = self._parse_screenshot_command(verification)

        if not url_path:
            return {
                **criterion,
                "passed": False,
                "verified_at": datetime.now(UTC).isoformat(),
                "verified_by": "browser",
                "verification_output": f"Could not parse URL path: {verification}",
            }

        # Resolve placeholders like {id}, {symbol} to real values
        resolved_path = await self._resolve_url_placeholders(url_path)
        if not resolved_path:
            return {
                **criterion,
                "passed": None,
                "verified_at": datetime.now(UTC).isoformat(),
                "verified_by": "manual_required",
                "verification_output": f"URL has unresolved placeholder: {url_path}. Requires manual verification.",
            }

        full_url = f"http://192.168.8.233:3000{resolved_path}"

        try:
            # Capture evidence using new comprehensive script
            result = await artifact_manager.capture_evidence(
                url=full_url,
                feature_id=feature_id,
                criterion_id=criterion_id,
            )

            if not result.get("success"):
                return {
                    **criterion,
                    "passed": False,
                    "verified_at": datetime.now(UTC).isoformat(),
                    "verified_by": "browser",
                    "verification_output": f"Evidence capture failed: {result.get('error', 'Unknown error')}",
                }

            # Save artifact record to database
            version = result.get("version", 1)
            file_size = sum(f.get("size", 0) for f in result.get("files", []))
            evidence_data = result.get("evidence", {})

            artifact_manager.save_artifact(
                feature_id=feature_id,
                criterion_id=criterion_id,
                version=version,
                file_path=f"{feature_id}/{criterion_id}/v{version}",
                file_size_bytes=file_size,
                evidence_data=evidence_data,
            )

            # Auto-detect failures from evidence
            console_errors = evidence_data.get("console", {}).get("errorCount", 0)
            network_failures = evidence_data.get("network", {}).get("failedRequests", 0)
            page_state = evidence_data.get("pageState", {})
            has_content = page_state.get("hasContent", True)
            error_messages = page_state.get("keyElements", {}).get("errorMessages", 0)

            # Auto-fail if obvious problems detected
            if network_failures > 0 or error_messages > 0 or not has_content:
                failure_reasons = []
                if network_failures > 0:
                    failures = evidence_data.get("network", {}).get("failures", [])
                    failure_reasons.append(f"{network_failures} network failures: {failures[:2]}")
                if error_messages > 0:
                    failure_reasons.append(f"{error_messages} error elements visible")
                if not has_content:
                    failure_reasons.append("Page has no content")

                return {
                    **criterion,
                    "passed": False,
                    "verified_at": datetime.now(UTC).isoformat(),
                    "verified_by": "auto",
                    "verification_output": f"Auto-failed: {'; '.join(failure_reasons)}. Artifact: {feature_id}/{criterion_id}/v{version}",
                }

            # Queue for visual verification
            artifact_ref = f"{feature_id}/{criterion_id}/v{version}"
            text_sample = page_state.get("visibleTextSample", "")[:100]
            warning_note = f" ({console_errors} console errors)" if console_errors > 0 else ""

            return {
                **criterion,
                "passed": None,  # Requires visual verification
                "verified_at": datetime.now(UTC).isoformat(),
                "verified_by": "pending_visual_review",
                "verification_output": f"NEEDS_VISUAL_REVIEW: {artifact_ref} ({file_size} bytes){warning_note}. Preview: {text_sample}",
            }

        except Exception as e:
            return {
                **criterion,
                "passed": False,
                "verified_at": datetime.now(UTC).isoformat(),
                "verified_by": "browser",
                "verification_output": f"Error: {str(e)[:MAX_OUTPUT_LENGTH]}",
            }

    async def _check_page_status(self, url: str) -> dict[str, Any]:
        """Check if page returns 200 status before taking screenshot.

        DEPRECATED: This method is no longer used. The new capture-evidence.js
        script handles page status checking via network request tracking.
        Kept for backward compatibility - will be removed in future version.

        Returns:
            Dict with ok=True if page loads, or ok=False with error message
        """
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                response = await client.get(url)

                if response.status_code == 404:
                    return {"ok": False, "error": f"HTTP 404 - Page not found: {url}"}
                if response.status_code >= 500:
                    return {"ok": False, "error": f"HTTP {response.status_code} - Server error"}
                if response.status_code >= 400:
                    return {"ok": False, "error": f"HTTP {response.status_code} - Client error"}

                # Check for Next.js 404 page in HTML content
                content = response.text[:2000].lower()
                if "404" in content and ("not found" in content or "page could not be found" in content):
                    return {"ok": False, "error": "Page contains 404 error content"}

                return {"ok": True, "status": response.status_code}

        except httpx.TimeoutException:
            return {"ok": False, "error": "Timeout checking page status"}
        except Exception as e:
            return {"ok": False, "error": f"Error checking page: {str(e)[:100]}"}

    async def _detect_error_screenshot(self, screenshot_path: Path, script_output: str) -> dict[str, Any]:
        """Detect if screenshot shows an error page.

        DEPRECATED: This method is no longer used. The new capture-evidence.js
        script captures page state including error messages, network failures,
        and console errors - providing much better error detection than file size heuristics.
        Kept for backward compatibility - will be removed in future version.

        Checks:
            1. Known error page file sizes (404 pages are often consistent size)
            2. Script output for error indicators
            3. File size patterns

        Returns:
            Dict with is_error=True/False and reason
        """
        file_size = screenshot_path.stat().st_size

        # Known 404 error page size from Next.js (approximately 33KB)
        # This is a heuristic based on observed 404 page screenshots
        KNOWN_404_SIZE = 33254
        KNOWN_404_TOLERANCE = 500  # Allow small variance

        if abs(file_size - KNOWN_404_SIZE) < KNOWN_404_TOLERANCE:
            return {
                "is_error": True,
                "reason": f"Screenshot size ({file_size}) matches known 404 error page pattern",
            }

        # Check script output for error indicators
        script_output_lower = script_output.lower()
        error_indicators = ["404", "not found", "error", "failed to load"]
        for indicator in error_indicators:
            if indicator in script_output_lower:
                return {
                    "is_error": True,
                    "reason": f"Script output contains error indicator: '{indicator}'",
                }

        return {"is_error": False, "reason": None}

    def _handle_manual_criterion(self, criterion: dict) -> dict[str, Any]:
        """Mark a criterion as requiring manual verification."""
        ctype = criterion.get("type", "unknown")
        return {
            **criterion,
            # Don't change passed - leave as-is for manual criteria
            "verified_by": "manual_required",
            "verification_output": f"Type '{ctype}' requires manual verification",
        }

    def _parse_curl_command(self, verification: str) -> tuple[str | None, str | None]:
        """Parse a curl command to extract URL and jq filter (legacy method).

        Returns:
            Tuple of (url, jq_filter) or (None, None) if parsing fails
        """
        parsed = self._parse_curl_command_full(verification)
        if parsed:
            return parsed.get("url"), parsed.get("jq_filter")
        return None, None

    def _parse_curl_command_full(self, verification: str) -> dict[str, Any] | None:
        """Parse a curl command to extract method, URL, data, and jq filter.

        Examples:
            curl -s http://localhost:8000/api/health | jq '.status'
            curl -s -X POST http://localhost:8000/api/data -d '{"key": "value"}'
            POST /api/strategies/{id}/evolve -> returns success

        Returns:
            Dict with url, method, data, jq_filter or None if parsing fails
        """
        result: dict[str, Any] = {"method": "GET"}

        # Handle shorthand format: "GET /api/path" or "POST /api/path"
        shorthand_match = re.match(
            r"^(GET|POST|PUT|PATCH|DELETE)\s+(/[^\s]+)", verification, re.IGNORECASE
        )
        if shorthand_match:
            result["method"] = shorthand_match.group(1).upper()
            result["url"] = f"http://localhost:8000{shorthand_match.group(2)}"
            return result

        # Extract HTTP method from -X flag
        method_match = re.search(r"-X\s+(GET|POST|PUT|PATCH|DELETE)", verification, re.IGNORECASE)
        if method_match:
            result["method"] = method_match.group(1).upper()

        # Extract URL
        url_match = re.search(r"http[s]?://[^\s|'\"]+", verification)
        if url_match:
            result["url"] = url_match.group(0)
        else:
            return None

        # Extract request data from -d flag
        data_match = re.search(r"-d\s+['\"]([^'\"]+)['\"]", verification)
        if data_match:
            try:
                result["data"] = json.loads(data_match.group(1))
            except json.JSONDecodeError:
                result["data"] = data_match.group(1)

        # Extract jq filter (handle both quoted and unquoted)
        jq_match = re.search(r"\|\s*jq\s+['\"]?(.+?)['\"]?\s*$", verification)
        if jq_match:
            result["jq_filter"] = jq_match.group(1).strip().strip("'\"")

        return result

    async def _apply_jq_cli(self, data: Any, jq_filter: str) -> Any:
        """Apply jq filter using the actual jq CLI for full compatibility.

        This supports all jq operations including:
            .field | length
            map(select(...))
            .items[] | select(.foo == "bar")
        """
        if not jq_filter or jq_filter == ".":
            return data

        try:
            # Write data to stdin and run jq
            proc = await asyncio.create_subprocess_exec(
                "jq",
                "-c",  # Compact output
                jq_filter,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            input_data = json.dumps(data).encode()
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=input_data), timeout=5
            )

            if proc.returncode != 0:
                logger.warning(
                    "jq_filter_failed",
                    filter=jq_filter,
                    error=stderr.decode()[:200],
                )
                # Fall back to simple parser for basic cases
                return self._apply_jq_filter_simple(data, jq_filter)

            # Parse jq output
            output = stdout.decode().strip()
            if not output or output == "null":
                return None

            try:
                return json.loads(output)
            except json.JSONDecodeError:
                # jq returned a raw string or number
                return output

        except FileNotFoundError:
            # jq not installed, fall back to simple parser
            logger.warning("jq_not_installed", fallback="simple_parser")
            return self._apply_jq_filter_simple(data, jq_filter)
        except TimeoutError:
            logger.warning("jq_timeout", filter=jq_filter)
            return None
        except Exception as e:
            logger.warning("jq_error", filter=jq_filter, error=str(e))
            return self._apply_jq_filter_simple(data, jq_filter)

    def _apply_jq_filter_simple(self, data: Any, jq_filter: str) -> Any:
        """Simple jq-like filter fallback (for when jq CLI unavailable)."""
        return self._apply_jq_filter(data, jq_filter)

    def _parse_pytest_command(self, verification: str) -> list[str] | None:
        """Parse a pytest command to extract arguments.

        Examples:
            pytest tests/agents/test_rules_validator.py
            pytest tests/ -k "test_watchlist"

        Returns:
            List of pytest arguments or None if parsing fails
        """
        # Remove 'pytest' prefix if present
        cmd = verification.strip()
        if cmd.startswith("pytest "):
            cmd = cmd[7:]
        elif cmd.startswith("pytest"):
            cmd = cmd[6:]
        else:
            return None

        # Split on spaces, but handle quoted strings
        parts = []
        current = ""
        in_quotes = False
        for char in cmd:
            if char in {'"', "'"}:
                in_quotes = not in_quotes
            elif char == " " and not in_quotes:
                if current:
                    parts.append(current)
                    current = ""
            else:
                current += char
        if current:
            parts.append(current)

        return parts if parts else None

    def _parse_screenshot_command(self, verification: str) -> str | None:
        """Parse a screenshot command to extract URL path.

        Examples:
            screenshot /dashboard and verify gauge visible
            screenshot /watchlist showing expanded row
            screenshot / and verify gauge visible

        Returns:
            URL path (e.g., /dashboard, /) or None if parsing fails
        """
        # Look for /path pattern (allow just / for root path)
        match = re.search(r"screenshot\s+(/[^\s]*)", verification, re.IGNORECASE)
        if match:
            path = match.group(1)
            # If path is just / or /?, return /
            return path if path else "/"
        return None

    async def _resolve_url_placeholders(self, url_path: str) -> str | None:
        """Resolve placeholders like {id}, {symbol} in URL paths for screenshots.

        UI Pattern Mappings:
            /backtest/{id} -> /backtest (no dynamic route - uses sidebar selection)
            /watchlist/{symbol} -> /watchlist?symbol=AAPL (uses query param for deep linking)
            /ideas/{id} -> /ideas/abc123 (has actual dynamic route)

        Returns:
            Resolved URL path or None if placeholder can't be resolved.
        """
        if "{" not in url_path:
            return url_path

        try:
            # /backtest/{id} - Use query param pattern: /backtest?runId=first
            # The backtest page now supports ?runId=X for deep linking
            if "/backtest/{id}" in url_path or ("/backtest/" in url_path and "{" in url_path):
                # Use ?runId=first to auto-select the first run
                resolved = "/backtest?runId=first"
                logger.info(
                    "backtest_url_resolved",
                    original=url_path,
                    resolved=resolved,
                    reason="Using ?runId=first for auto-selection",
                )
                return resolved

            # /watchlist/{symbol} - NO dynamic route. Uses query param for deep linking
            if "/watchlist/{symbol}" in url_path:
                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.get("http://localhost:8000/api/watchlist/")
                    if resp.status_code == 200:
                        data = resp.json()
                        items = data.get("items", data) if isinstance(data, dict) else data
                        if items and len(items) > 0:
                            symbol = items[0].get("symbol", "AAPL")
                            resolved = f"/watchlist?symbol={symbol}"
                            logger.info(
                                "watchlist_url_resolved",
                                original=url_path,
                                resolved=resolved,
                                reason="Using query param for row expansion",
                            )
                            return resolved
                # Default if no watchlist items
                return "/watchlist?symbol=AAPL"

            # /ideas/{id} - Has actual dynamic route at /ideas/[id]
            if "/ideas/{id}" in url_path:
                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.get("http://localhost:8000/api/ideas/")
                    if resp.status_code == 200:
                        ideas = resp.json()
                        if ideas and len(ideas) > 0:
                            idea_id = str(ideas[0].get("id", ideas[0].get("idea_id", 1)))
                            return url_path.replace("{id}", idea_id)
                # No ideas - return None to skip (can't verify without data)
                logger.warning("no_ideas_for_verification", url_path=url_path)
                return None

            # /strategies/{id} - Use query param for modal display
            if "/strategies/{id}" in url_path or ("/strategies/" in url_path and "{" in url_path):
                resolved = "/strategies?id=first"
                logger.info(
                    "strategies_url_resolved",
                    original=url_path,
                    resolved=resolved,
                    reason="Using ?id=first for modal display",
                )
                return resolved

            # /trading with tab - Use query param for tab selection
            if "/trading/{tab}" in url_path or ("/trading/" in url_path and "{" in url_path):
                # Default to closed tab to show historical trades
                resolved = "/trading?tab=closed"
                logger.info(
                    "trading_url_resolved",
                    original=url_path,
                    resolved=resolved,
                    reason="Using ?tab=closed for historical trades view",
                )
                return resolved

            # Unresolved placeholder - return None to skip auto-capture
            logger.warning("unresolved_url_placeholder", url_path=url_path)
            return None

        except Exception as e:
            logger.warning("placeholder_resolution_failed", url_path=url_path, error=str(e))
            return None

    async def _resolve_api_placeholders(self, verification: str) -> str:
        """Resolve placeholders like {id}, {run_id}, {symbol} in API verification commands.

        Examples:
            curl http://localhost:8000/api/backtest/runs/{id} -> curl .../runs/abc123
            curl http://localhost:8000/api/backtest/monte-carlo/{run_id} -> curl .../monte-carlo/abc123

        Returns:
            Verification string with placeholders resolved, or original if resolution fails.
        """
        if "{" not in verification:
            return verification

        resolved = verification

        try:
            # Resolve {id} or {run_id} for backtest API endpoints
            if "{id}" in resolved or "{run_id}" in resolved:
                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.get("http://localhost:8000/api/backtest/runs")
                    if resp.status_code == 200:
                        runs = resp.json()
                        if runs and len(runs) > 0:
                            run_id = runs[0].get("id", "")
                            resolved = resolved.replace("{id}", run_id)
                            resolved = resolved.replace("{run_id}", run_id)
                            logger.info(
                                "api_placeholder_resolved",
                                placeholder="{id}/{run_id}",
                                value=run_id,
                            )

            # Resolve {symbol} for analytics/watchlist endpoints
            if "{symbol}" in resolved:
                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.get("http://localhost:8000/api/watchlist/")
                    if resp.status_code == 200:
                        data = resp.json()
                        items = data.get("items", data) if isinstance(data, dict) else data
                        if items and len(items) > 0:
                            symbol = items[0].get("symbol", "AAPL")
                            resolved = resolved.replace("{symbol}", symbol)
                            logger.info(
                                "api_placeholder_resolved",
                                placeholder="{symbol}",
                                value=symbol,
                            )

            # Resolve {agent_id} for agent state endpoints
            if "{agent_id}" in resolved:
                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.get("http://localhost:8000/api/agents/telemetry/history?limit=1")
                    if resp.status_code == 200:
                        data = resp.json()
                        runs = data.get("runs", [])
                        if runs and len(runs) > 0:
                            agent_id = runs[0].get("id", "")
                            resolved = resolved.replace("{agent_id}", agent_id)

            # Resolve {provider} for source endpoints
            if "{provider}" in resolved:
                resolved = resolved.replace("{provider}", "yfinance")

            # Resolve {tool_name} for MCP endpoints
            if "{tool_name}" in resolved:
                resolved = resolved.replace("{tool_name}", "list_tools")

            # Resolve {task_id} with a placeholder (would need actual task)
            if "{task_id}" in resolved:
                # Can't resolve without context - leave as-is and let it fail gracefully
                logger.warning("unresolved_task_id_placeholder", verification=verification)

            return resolved

        except Exception as e:
            logger.warning(
                "api_placeholder_resolution_failed",
                verification=verification[:100],
                error=str(e),
            )
            return verification  # Return original if resolution fails

    def _is_url_allowed(self, url: str) -> bool:
        """Check if URL matches allowed patterns."""
        return any(re.match(pattern, url) for pattern in ALLOWED_URL_PATTERNS)

    def _apply_jq_filter(self, data: Any, jq_filter: str) -> Any:
        """Apply a simple jq-like filter to JSON data.

        Supports:
            .field - extract field
            .field.nested - nested field
            {a: .a, b: .b} - object projection
            . - return as-is
        """
        if not jq_filter or jq_filter == ".":
            return data

        # Handle object projection {a: .a, b: .b}
        if jq_filter.startswith("{") and jq_filter.endswith("}"):
            inner = jq_filter[1:-1].strip()
            result = {}
            for part in inner.split(","):
                if ":" in part:
                    key, path = part.split(":", 1)
                    key = key.strip()
                    path = path.strip()
                    if path.startswith("."):
                        result[key] = self._apply_jq_filter(data, path)
                    else:
                        result[key] = path
            return result

        # Handle .field.nested
        if jq_filter.startswith("."):
            fields = jq_filter[1:].split(".")
            current = data
            for field in fields:
                if not field:
                    continue
                if isinstance(current, dict) and field in current:
                    current = current[field]
                elif isinstance(current, list) and field.isdigit():
                    idx = int(field)
                    if 0 <= idx < len(current):
                        current = current[idx]
                    else:
                        return None
                else:
                    return None
            return current

        return data

    async def _save_criterion_result(
        self, feature_id: str, result: dict[str, Any]
    ) -> bool:
        """Save verification result to database."""
        criterion_id = result.get("id")
        if not criterion_id:
            return False

        try:
            with self.conn_mgr.connection() as conn:
                # Update the specific criterion in JSONB array
                conn.execute(
                    """
                    UPDATE feature_capabilities
                    SET acceptance_criteria = (
                        SELECT jsonb_agg(
                            CASE
                                WHEN c->>'id' = %s THEN
                                    c || jsonb_build_object(
                                        'passed', %s::boolean,
                                        'verified_at', %s,
                                        'verified_by', %s,
                                        'verification_output', %s
                                    )
                                ELSE c
                            END
                        )
                        FROM jsonb_array_elements(acceptance_criteria) c
                    ),
                    updated_at = NOW()
                    WHERE feature_id = %s
                    """,
                    (
                        criterion_id,
                        result.get("passed"),
                        result.get("verified_at"),
                        result.get("verified_by"),
                        result.get("verification_output"),
                        feature_id,
                    ),
                )
                conn.commit()
                return True

        except Exception as e:
            logger.error(
                "save_criterion_result_failed",
                feature_id=feature_id,
                criterion_id=criterion_id,
                error=str(e),
            )
            return False
