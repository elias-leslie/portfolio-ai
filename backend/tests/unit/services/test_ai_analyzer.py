"""Unit tests for AI capability analyzer."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.services.ai_analyzer import CapabilityAnalyzer


class TestCapabilityAnalyzer:
    """Test CapabilityAnalyzer class."""

    @pytest.fixture
    def mock_conn_mgr(self) -> MagicMock:
        """Create mock ConnectionManager."""
        return MagicMock()

    @pytest.fixture
    def mock_config(self) -> dict:
        """Create mock config dict."""
        return {
            "scan_config": {
                "targets": {},
                "ai_analysis": {
                    "enabled": True,
                    "model": "claude-sonnet-4.5",
                    "confidence_threshold": 0.70,
                },
            }
        }

    @pytest.fixture
    def mock_capabilities(self) -> dict:
        """Create mock capabilities data."""
        return {
            "db_capabilities": [
                {
                    "id": 1,
                    "table_name": "news_cache",
                    "category": "news",
                    "row_count": 100,
                    "total_columns": 10,
                    "columns": ["id", "title", "content"],
                    "columns_with_data": ["id", "title"],
                    "columns_mostly_null": ["content"],
                    "completeness_pct": 67,
                    "date_range_start": "2025-01-01",
                    "date_range_end": "2025-01-05",
                    "expected_freshness": "hourly",
                    "days_since_update": 5,
                    "freshness_status": "stale",
                    "last_scanned_at": "2025-01-10T00:00:00+00:00",
                }
            ],
            "celery_capabilities": [
                {
                    "id": 1,
                    "task_name": "fetch-news",
                    "category": "news",
                    "task_path": "app.tasks.news_tasks.fetch_news",
                    "function_name": "fetch_news",
                    "schedule_description": "Daily at 03:00 UTC",
                    "schedule_crontab": "0 3 * * *",
                    "schedule_interval_seconds": 86400,
                    "last_run_at": "2025-01-09T03:00:00+00:00",
                    "next_run_at": None,
                    "success_count_7d": 5,
                    "failure_count_7d": 2,
                    "success_rate_pct": 71,
                    "avg_duration_ms": None,
                    "max_duration_ms": None,
                    "populates_tables": ["news_cache"],
                    "depends_on_tasks": [],
                    "last_scanned_at": "2025-01-10T00:00:00+00:00",
                }
            ],
            "api_capabilities": [
                {
                    "id": 1,
                    "endpoint_path": "/api/news",
                    "http_method": "GET",
                    "category": "news",
                    "route_file": "news.py",
                    "function_name": "get_news",
                    "depends_on_tables": ["news_cache"],
                    "avg_response_time_ms": None,
                    "p95_response_time_ms": None,
                    "p99_response_time_ms": None,
                    "error_rate_pct": None,
                    "last_7d_request_count": None,
                    "last_scanned_at": "2025-01-10T00:00:00+00:00",
                }
            ],
        }

    def test_init_with_llm_client(self, mock_conn_mgr: MagicMock, mock_config: dict) -> None:
        """Test initialization with LLM client available."""
        with (
            patch("shutil.which", return_value="/usr/local/bin/claude"),
            patch(
                "app.services.ai_analyzer.load_capabilities_config",
                return_value=mock_config,
            ),
        ):
            analyzer = CapabilityAnalyzer(mock_conn_mgr)

            assert analyzer.conn_mgr == mock_conn_mgr
            assert analyzer.enabled is True
            assert analyzer.model == "claude-sonnet-4.5"
            assert analyzer.confidence_threshold == 0.70
            assert analyzer.llm_client is not None

    def test_init_without_llm_client(self, mock_conn_mgr: MagicMock, mock_config: dict) -> None:
        """Test initialization without LLM client."""
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("shutil.which", return_value=None),
            patch("os.path.isfile", return_value=False),
            patch(
                "app.services.ai_analyzer.load_capabilities_config",
                return_value=mock_config,
            ),
        ):
            analyzer = CapabilityAnalyzer(mock_conn_mgr)

            assert analyzer.llm_client is None

    def test_analyze_disabled(self, mock_conn_mgr: MagicMock, mock_config: dict) -> None:
        """Test analyze returns empty list when disabled."""
        mock_config["scan_config"]["ai_analysis"]["enabled"] = False

        with patch(
            "app.services.ai_analyzer.load_capabilities_config",
            return_value=mock_config,
        ):
            analyzer = CapabilityAnalyzer(mock_conn_mgr)
            result = analyzer.analyze()

            assert result == []

    def test_analyze_no_llm_client(self, mock_conn_mgr: MagicMock, mock_config: dict) -> None:
        """Test analyze returns empty list when no LLM client."""
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("shutil.which", return_value=None),
            patch("os.path.isfile", return_value=False),
            patch(
                "app.services.ai_analyzer.load_capabilities_config",
                return_value=mock_config,
            ),
        ):
            analyzer = CapabilityAnalyzer(mock_conn_mgr)
            result = analyzer.analyze()

            assert result == []

    def test_load_capabilities(
        self,
        mock_conn_mgr: MagicMock,
        mock_config: dict,
        mock_capabilities: dict,
    ) -> None:
        """Test loading capabilities from database."""
        mock_conn = MagicMock()
        mock_conn_mgr.connection.return_value.__enter__.return_value = mock_conn

        # Mock database queries
        db_result = MagicMock()
        db_result.fetchall.return_value = [
            (
                1,
                "news_cache",
                "news",
                100,
                10,
                ["id", "title", "content"],
                ["id", "title"],
                ["content"],
                67,
                datetime(2025, 1, 1).date(),
                datetime(2025, 1, 5).date(),
                "hourly",
                5,
                "stale",
                datetime(2025, 1, 10, tzinfo=UTC),
            )
        ]

        celery_result = MagicMock()
        celery_result.fetchall.return_value = [
            (
                1,
                "fetch-news",
                "news",
                "app.tasks.news_tasks.fetch_news",
                "fetch_news",
                "Daily at 03:00 UTC",
                "0 3 * * *",
                86400,
                datetime(2025, 1, 9, 3, 0, tzinfo=UTC),
                None,
                5,
                2,
                71,
                None,
                None,
                ["news_cache"],
                [],
                datetime(2025, 1, 10, tzinfo=UTC),
            )
        ]

        api_result = MagicMock()
        api_result.fetchall.return_value = [
            (
                1,
                "/api/news",
                "GET",
                "news",
                "news.py",
                "get_news",
                ["news_cache"],
                None,
                None,
                None,
                None,
                None,
                datetime(2025, 1, 10, tzinfo=UTC),
            )
        ]

        mock_conn.execute.side_effect = [db_result, celery_result, api_result]

        with patch(
            "app.services.ai_analyzer.load_capabilities_config",
            return_value=mock_config,
        ):
            analyzer = CapabilityAnalyzer(mock_conn_mgr)
            capabilities = analyzer.load_capabilities()

            assert len(capabilities["db_capabilities"]) == 1
            assert len(capabilities["celery_capabilities"]) == 1
            assert len(capabilities["api_capabilities"]) == 1

    def test_build_prompt(
        self,
        mock_conn_mgr: MagicMock,
        mock_config: dict,
        mock_capabilities: dict,
    ) -> None:
        """Test building AI prompt with capabilities."""
        with patch(
            "app.services.ai_analyzer.load_capabilities_config",
            return_value=mock_config,
        ):
            analyzer = CapabilityAnalyzer(mock_conn_mgr)
            prompt = analyzer.build_prompt(mock_capabilities)

            assert "Database Capabilities" in prompt
            assert "Celery Tasks" in prompt
            assert "API Endpoints" in prompt
            assert "news_cache" in prompt
            assert "fetch-news" in prompt
            assert "/api/news" in prompt
            assert "Return a JSON array" in prompt

    def test_llm_client_integration(self, mock_conn_mgr: MagicMock, mock_config: dict) -> None:
        """Test LLM client integration in analyze method."""
        from app.agents.llm_client import LLMResponse

        mock_response = LLMResponse(
            content='[{"capability_type": "db", "ai_confidence": 0.85}]',
            provider="gemini",
            model="gemini-2.5-pro",
            usage={"total_tokens": 100},
        )

        with patch(
            "app.services.ai_analyzer.load_capabilities_config",
            return_value=mock_config,
        ):
            analyzer = CapabilityAnalyzer(mock_conn_mgr)

            # Mock methods with proper structure
            analyzer.load_capabilities = MagicMock(
                return_value={
                    "db_capabilities": [],
                    "celery_capabilities": [],
                    "api_capabilities": [],
                }
            )
            analyzer.llm_client.generate = MagicMock(return_value=mock_response)
            analyzer.save_insights = MagicMock(return_value=1)

            result = analyzer.analyze()

            # Verify LLM client was called
            analyzer.llm_client.generate.assert_called_once()
            assert len(result) == 1
            assert result[0]["capability_type"] == "db"

    def test_parse_ai_response_valid_json(
        self, mock_conn_mgr: MagicMock, mock_config: dict
    ) -> None:
        """Test parsing valid JSON response."""
        response = """
[
  {
    "capability_type": "db",
    "capability_id": 1,
    "table_name": "news_cache",
    "insight_type": "freshness",
    "severity": "high",
    "finding": "Data is stale",
    "ai_confidence": 0.85
  }
]
"""

        with patch(
            "app.services.ai_analyzer.load_capabilities_config",
            return_value=mock_config,
        ):
            analyzer = CapabilityAnalyzer(mock_conn_mgr)
            insights = analyzer.parse_ai_response(response)

            assert len(insights) == 1
            assert insights[0]["capability_type"] == "db"
            assert insights[0]["table_name"] == "news_cache"

    def test_parse_ai_response_with_markdown_fences(
        self, mock_conn_mgr: MagicMock, mock_config: dict
    ) -> None:
        """Test parsing JSON response with markdown code fences."""
        response = """```json
[{"capability_type": "db", "insight_type": "freshness"}]
```"""

        with patch(
            "app.services.ai_analyzer.load_capabilities_config",
            return_value=mock_config,
        ):
            analyzer = CapabilityAnalyzer(mock_conn_mgr)
            insights = analyzer.parse_ai_response(response)

            assert len(insights) == 1
            assert insights[0]["capability_type"] == "db"

    def test_parse_ai_response_invalid_json(
        self, mock_conn_mgr: MagicMock, mock_config: dict
    ) -> None:
        """Test parsing invalid JSON response."""
        response = "This is not valid JSON"

        with patch(
            "app.services.ai_analyzer.load_capabilities_config",
            return_value=mock_config,
        ):
            analyzer = CapabilityAnalyzer(mock_conn_mgr)

            with pytest.raises(ValueError) as exc_info:
                analyzer.parse_ai_response(response)

            assert "failed to parse" in str(exc_info.value).lower()

    def test_parse_ai_response_not_array(self, mock_conn_mgr: MagicMock, mock_config: dict) -> None:
        """Test parsing JSON that's not an array."""
        response = '{"not": "an array"}'

        with patch(
            "app.services.ai_analyzer.load_capabilities_config",
            return_value=mock_config,
        ):
            analyzer = CapabilityAnalyzer(mock_conn_mgr)

            with pytest.raises(ValueError) as exc_info:
                analyzer.parse_ai_response(response)

            assert "must be a json array" in str(exc_info.value).lower()

    def test_save_insights_upsert(self, mock_conn_mgr: MagicMock, mock_config: dict) -> None:
        """Test saving insights with UPSERT logic."""
        mock_conn = MagicMock()
        mock_conn_mgr.connection.return_value.__enter__.return_value = mock_conn

        insights = [
            {
                "capability_type": "db",
                "capability_id": 1,
                "table_name": "news_cache",
                "insight_type": "freshness",
                "severity": "high",
                "finding": "Data is stale",
                "expected_behavior": "Should update hourly",
                "actual_behavior": "Last updated 5 days ago",
                "impact": "Users see outdated news",
                "suggested_fix": "Check news fetch task",
                "reference_data": {"tables": ["news_cache"]},
                "ai_confidence": 0.85,
            }
        ]

        with patch(
            "app.services.ai_analyzer.load_capabilities_config",
            return_value=mock_config,
        ):
            analyzer = CapabilityAnalyzer(mock_conn_mgr)
            count = analyzer.save_insights(insights)

            assert count == 1
            assert mock_conn.execute.call_count == 1
            mock_conn.commit.assert_called_once()

    def test_save_insights_empty_list(self, mock_conn_mgr: MagicMock, mock_config: dict) -> None:
        """Test saving empty insights list."""
        mock_conn = MagicMock()
        mock_conn_mgr.connection.return_value.__enter__.return_value = mock_conn

        with patch(
            "app.services.ai_analyzer.load_capabilities_config",
            return_value=mock_config,
        ):
            analyzer = CapabilityAnalyzer(mock_conn_mgr)
            count = analyzer.save_insights([])

            # Should still work (no execute calls)
            assert count == 0

    def test_analyze_filters_by_confidence(
        self, mock_conn_mgr: MagicMock, mock_config: dict
    ) -> None:
        """Test that analyze filters insights by confidence threshold."""
        from app.agents.llm_client import LLMResponse

        mock_config["scan_config"]["ai_analysis"]["confidence_threshold"] = 0.80

        mock_insights = [
            {"ai_confidence": 0.90, "table_name": "high_confidence"},  # Keep
            {"ai_confidence": 0.75, "table_name": "medium_confidence"},  # Filter out
            {"ai_confidence": 0.85, "table_name": "acceptable"},  # Keep
        ]

        mock_response = LLMResponse(
            content="[]",
            provider="gemini",
            model="gemini-2.5-pro",
            usage={"total_tokens": 100},
        )

        with patch(
            "app.services.ai_analyzer.load_capabilities_config",
            return_value=mock_config,
        ):
            analyzer = CapabilityAnalyzer(mock_conn_mgr)

            # Mock the methods
            analyzer.load_capabilities = MagicMock(return_value={})
            analyzer.build_prompt = MagicMock(return_value="test prompt")
            analyzer.llm_client.generate = MagicMock(return_value=mock_response)
            analyzer.parse_ai_response = MagicMock(return_value=mock_insights)
            analyzer.save_insights = MagicMock(return_value=2)

            result = analyzer.analyze()

            # Should only save 2 insights (confidence >= 0.80)
            saved_insights = analyzer.save_insights.call_args[0][0]
            assert len(saved_insights) == 2
            assert all(i["ai_confidence"] >= 0.80 for i in saved_insights)
