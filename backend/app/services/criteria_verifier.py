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
SCREENSHOT_DIR = Path("/tmp/criteria-screenshots")

# Auto-verifiable types
AUTO_VERIFIABLE_TYPES = {"api", "test", "ui"}
MANUAL_ONLY_TYPES = {"backend", "quality", "db", "content"}


class CriteriaVerifier:
    """Auto-verification engine for acceptance criteria."""

    def __init__(self) -> None:
        """Initialize the verifier."""
        self.conn_mgr = get_connection_manager()
        # Ensure screenshot directory exists
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

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
        """
        verification = criterion.get("verification", "")

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
        """Verify a UI criterion by taking a screenshot.

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

        screenshot_path = SCREENSHOT_DIR / f"{feature_id}-{criterion_id}.png"
        full_url = f"http://192.168.8.233:3000{url_path}"

        try:
            # Run screenshot script
            proc = await asyncio.create_subprocess_exec(
                "node",
                str(BROWSER_SCRIPTS / "screenshot.js"),
                full_url,
                str(screenshot_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                _stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=MAX_UI_TIMEOUT
                )
            except TimeoutError:
                proc.kill()
                return {
                    **criterion,
                    "passed": False,
                    "verified_at": datetime.now(UTC).isoformat(),
                    "verified_by": "browser",
                    "verification_output": f"Timeout after {MAX_UI_TIMEOUT}s",
                }

            # Check if screenshot was created and has content
            if screenshot_path.exists() and screenshot_path.stat().st_size > 1000:
                return {
                    **criterion,
                    "passed": True,
                    "verified_at": datetime.now(UTC).isoformat(),
                    "verified_by": "browser",
                    "verification_output": f"Screenshot saved: {screenshot_path}",
                }
            return {
                **criterion,
                "passed": False,
                "verified_at": datetime.now(UTC).isoformat(),
                "verified_by": "browser",
                "verification_output": f"Screenshot failed or too small. stderr: {stderr.decode()[:500]}",
            }

        except Exception as e:
            return {
                **criterion,
                "passed": False,
                "verified_at": datetime.now(UTC).isoformat(),
                "verified_by": "browser",
                "verification_output": f"Error: {str(e)[:MAX_OUTPUT_LENGTH]}",
            }

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

        Returns:
            URL path (e.g., /dashboard) or None if parsing fails
        """
        # Look for /path pattern
        match = re.search(r"screenshot\s+(/[^\s]+)", verification, re.IGNORECASE)
        return match.group(1) if match else None

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
