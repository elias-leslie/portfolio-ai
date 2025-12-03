"""AI-powered capability analysis service.

This module uses dual-provider LLM clients (Gemini + Claude CLI) to analyze
system capabilities and generate insights about data quality, missing capabilities,
and broken dependencies.

Zero API costs - uses local CLI tools with automatic failover.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from ..agents.llm_client import DualProviderClient
from ..logging_config import get_logger
from ..storage.connection import ConnectionManager
from .config_loader import load_capabilities_config

logger = get_logger(__name__)


class CapabilityAnalyzer:
    """Analyzes system capabilities using AI to identify issues and gaps.

    Uses Claude Code CLI to review database, Celery, and API capabilities,
    generating actionable insights about data quality, freshness, and gaps.

    Zero API cost - uses local Claude Code CLI instead of Anthropic API.
    """

    def __init__(self, conn_mgr: ConnectionManager) -> None:
        """Initialize analyzer with database connection and dual-provider LLM client.

        Args:
            conn_mgr: Database connection manager
        """
        self.conn_mgr = conn_mgr
        self.config = load_capabilities_config()

        # Load AI config
        ai_config = self.config.get("scan_config", {}).get("ai_analysis", {})
        self.enabled = ai_config.get("enabled", True)
        self.model = ai_config.get("model", "claude-sonnet-4.5")
        self.confidence_threshold = ai_config.get("confidence_threshold", 0.70)

        # Initialize dual-provider LLM client (Gemini primary, Claude fallback)
        try:
            self.llm_client: DualProviderClient | None = DualProviderClient(primary="gemini")
            logger.info("llm_client_initialized", providers=["gemini", "claude"])
        except RuntimeError as e:
            logger.warning("llm_client_unavailable", error=str(e))
            self.llm_client = None

    def analyze(self) -> list[dict[str, Any]]:
        """Run full AI analysis pipeline.

        Returns:
            List of insight dicts that were saved to database
        """
        if not self.enabled:
            logger.info("ai_analysis_disabled")
            return []

        if not self.llm_client:
            logger.error("ai_analysis_skipped", reason="LLM client not available")
            return []

        logger.info("ai_analysis_started")

        try:
            # Load all capabilities
            capabilities = self.load_capabilities()

            # Build prompt
            prompt = self.build_prompt(capabilities)

            # Call LLM with dual-provider client (Gemini primary, Claude fallback)
            logger.info("calling_llm_client", prompt_length=len(prompt))
            response = self.llm_client.generate(prompt=prompt)
            ai_response = response.content

            logger.info(
                "llm_response_received",
                provider=response.provider,
                model=response.model,
                tokens=response.usage.get("total_tokens", 0),
                response_length=len(ai_response),
            )

            # Parse response
            insights = self.parse_ai_response(ai_response)

            # Filter by confidence threshold
            filtered_insights = [
                i for i in insights if i.get("ai_confidence", 0) >= self.confidence_threshold
            ]

            logger.info(
                "ai_analysis_insights_parsed",
                total_insights=len(insights),
                filtered_insights=len(filtered_insights),
                confidence_threshold=self.confidence_threshold,
            )

            # Save to database
            saved_count = self.save_insights(filtered_insights)

            logger.info("ai_analysis_complete", insights_saved=saved_count)

            return filtered_insights

        except Exception as e:
            logger.error("ai_analysis_failed", error=str(e))
            raise

    def load_capabilities(self) -> dict[str, list[dict[str, Any]]]:
        """Load all capabilities from database.

        Returns:
            Dict with keys: db_capabilities, celery_capabilities, api_capabilities
        """
        with self.conn_mgr.connection() as conn:
            # Load database capabilities
            result = conn.execute("""
                SELECT
                    id, table_name, category, row_count, total_columns,
                    columns, columns_with_data, columns_mostly_null,
                    completeness_pct, date_range_start, date_range_end,
                    expected_freshness, days_since_update, freshness_status,
                    last_scanned_at
                FROM db_capabilities
                ORDER BY table_name
            """)
            db_caps = [
                {
                    "id": row[0],
                    "table_name": row[1],
                    "category": row[2],
                    "row_count": row[3],
                    "total_columns": row[4],
                    "columns": row[5],
                    "columns_with_data": row[6],
                    "columns_mostly_null": row[7],
                    "completeness_pct": row[8],
                    "date_range_start": row[9].isoformat()
                    if isinstance(row[9], datetime)
                    else None,
                    "date_range_end": row[10].isoformat()
                    if isinstance(row[10], datetime)
                    else None,
                    "expected_freshness": row[11],
                    "days_since_update": row[12],
                    "freshness_status": row[13],
                    "last_scanned_at": row[14].isoformat()
                    if isinstance(row[14], datetime)
                    else None,
                }
                for row in result.fetchall()
            ]

            # Load Celery capabilities
            result = conn.execute("""
                SELECT
                    id, task_name, category, task_path, function_name,
                    schedule_description, schedule_crontab, schedule_interval_seconds,
                    last_run_at, next_run_at, success_count_7d, failure_count_7d,
                    success_rate_pct, avg_duration_ms, max_duration_ms,
                    populates_tables, depends_on_tasks, last_scanned_at
                FROM celery_capabilities
                ORDER BY task_name
            """)
            celery_caps = [
                {
                    "id": row[0],
                    "task_name": row[1],
                    "category": row[2],
                    "task_path": row[3],
                    "function_name": row[4],
                    "schedule_description": row[5],
                    "schedule_crontab": row[6],
                    "schedule_interval_seconds": row[7],
                    "last_run_at": row[8].isoformat() if isinstance(row[8], datetime) else None,
                    "next_run_at": row[9].isoformat() if isinstance(row[9], datetime) else None,
                    "success_count_7d": row[10],
                    "failure_count_7d": row[11],
                    "success_rate_pct": row[12],
                    "avg_duration_ms": row[13],
                    "max_duration_ms": row[14],
                    "populates_tables": row[15],
                    "depends_on_tasks": row[16],
                    "last_scanned_at": row[17].isoformat()
                    if isinstance(row[17], datetime)
                    else None,
                }
                for row in result.fetchall()
            ]

            # Load API capabilities
            result = conn.execute("""
                SELECT
                    id, endpoint_path, http_method, category, route_file,
                    function_name, depends_on_tables, avg_response_time_ms,
                    p95_response_time_ms, p99_response_time_ms, error_rate_pct,
                    last_7d_request_count, last_scanned_at
                FROM api_capabilities
                ORDER BY endpoint_path, http_method
            """)
            api_caps = [
                {
                    "id": row[0],
                    "endpoint_path": row[1],
                    "http_method": row[2],
                    "category": row[3],
                    "route_file": row[4],
                    "function_name": row[5],
                    "depends_on_tables": row[6],
                    "avg_response_time_ms": row[7],
                    "p95_response_time_ms": row[8],
                    "p99_response_time_ms": row[9],
                    "error_rate_pct": float(row[10]) if row[10] else None,
                    "last_7d_request_count": row[11],
                    "last_scanned_at": row[12].isoformat()
                    if isinstance(row[12], datetime)
                    else None,
                }
                for row in result.fetchall()
            ]

            logger.info(
                "capabilities_loaded",
                db_tables=len(db_caps),
                celery_tasks=len(celery_caps),
                api_endpoints=len(api_caps),
            )

            return {
                "db_capabilities": db_caps,
                "celery_capabilities": celery_caps,
                "api_capabilities": api_caps,
            }

    def build_prompt(self, capabilities: dict[str, list[dict[str, Any]]]) -> str:
        """Build AI prompt with capability data.

        Args:
            capabilities: Dict with db_capabilities, celery_capabilities, api_capabilities

        Returns:
            Formatted prompt string for Claude API
        """
        prompt = """You are analyzing a system capabilities registry for a portfolio analytics platform. Review the data and identify:

1. **Data quality issues** (stale data, incomplete data, missing fields)
2. **Missing capabilities** (gaps in data sources, missing scheduled tasks)
3. **Broken dependencies** (tasks failing, endpoints potentially broken, data pipelines interrupted)

**Context:**
- This is a real-time portfolio analytics system with market data, news, and portfolio tracking
- Tables should be fresh (see expected_freshness field)
- Celery tasks should have high success rates (>95%)
- Critical data pipelines must be monitored

---

## Database Capabilities

"""
        prompt += json.dumps(capabilities["db_capabilities"], indent=2)

        prompt += "\n\n---\n\n## Celery Tasks\n\n"
        prompt += json.dumps(capabilities["celery_capabilities"], indent=2)

        prompt += "\n\n---\n\n## API Endpoints\n\n"
        prompt += json.dumps(capabilities["api_capabilities"], indent=2)

        prompt += """

---

## Instructions

Return a JSON array of insights. Each insight should have this structure:

```json
{
  "capability_type": "db|celery|api|missing",
  "capability_id": <id or null if missing capability>,
  "table_name": "table or task or endpoint name",
  "insight_type": "data_quality|freshness|missing_data|missing_capability|broken_dependency",
  "severity": "critical|high|medium|low",
  "finding": "Brief description of the issue (1-2 sentences)",
  "expected_behavior": "What should happen",
  "actual_behavior": "What's actually happening",
  "impact": "Trading/business impact (1-2 sentences)",
  "suggested_fix": "Specific fix with file paths if applicable",
  "reference_data": {
    "files": ["backend/app/tasks/market_data_tasks.py"],
    "tables": ["market_data"],
    "tasks": ["fetch_market_data"]
  },
  "ai_confidence": 0.85
}
```

**Important:**
- Only return insights with confidence >= 0.70
- Focus on actionable, specific findings
- Include file paths in suggested_fix when possible
- Use "missing" capability_type for gaps (e.g., no task to refresh a stale table)
- Be concise but specific

Return ONLY the JSON array, no additional text.
"""

        return prompt

    def parse_ai_response(self, response: str) -> list[dict[str, Any]]:
        """Parse AI response into structured insights.

        Args:
            response: Raw AI response text

        Returns:
            List of insight dicts

        Raises:
            ValueError: If response is not valid JSON
        """
        # Remove markdown code fences if present
        cleaned = response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        cleaned = cleaned.strip()

        try:
            insights = json.loads(cleaned)

            if not isinstance(insights, list):
                raise ValueError("AI response must be a JSON array")

            logger.info("ai_response_parsed", insight_count=len(insights))

            return insights

        except json.JSONDecodeError as e:
            logger.error("ai_response_parse_failed", error=str(e), response_preview=response[:200])
            raise ValueError(f"Failed to parse AI response as JSON: {e}") from e

    def save_insights(self, insights: list[dict[str, Any]]) -> int:
        """Save insights to database with UPSERT logic.

        Args:
            insights: List of insight dicts

        Returns:
            Number of insights saved
        """
        with self.conn_mgr.connection() as conn:
            try:
                for insight in insights:
                    # Extract fields
                    capability_type = insight.get("capability_type")
                    capability_id = insight.get("capability_id")
                    table_name = insight.get("table_name")
                    insight_type = insight.get("insight_type")
                    severity = insight.get("severity")
                    finding = insight.get("finding")
                    expected_behavior = insight.get("expected_behavior")
                    actual_behavior = insight.get("actual_behavior")
                    impact = insight.get("impact")
                    suggested_fix = insight.get("suggested_fix")
                    reference_data = json.dumps(insight.get("reference_data", {}))
                    ai_confidence = insight.get("ai_confidence")

                    # UPSERT: ON CONFLICT preserve status field
                    # Uses (capability_type, table_name, insight_type) constraint
                    # instead of capability_id which changes on rescan
                    conn.execute(
                        """
                        INSERT INTO capability_insights (
                            capability_type, capability_id, table_name, insight_type,
                            severity, finding, expected_behavior, actual_behavior,
                            impact, suggested_fix, reference_data, ai_model,
                            ai_confidence, status, generated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s
                        )
                        ON CONFLICT (capability_type, table_name, insight_type)
                        DO UPDATE SET
                            capability_id = EXCLUDED.capability_id,
                            severity = EXCLUDED.severity,
                            finding = EXCLUDED.finding,
                            expected_behavior = EXCLUDED.expected_behavior,
                            actual_behavior = EXCLUDED.actual_behavior,
                            impact = EXCLUDED.impact,
                            suggested_fix = EXCLUDED.suggested_fix,
                            reference_data = EXCLUDED.reference_data,
                            ai_model = EXCLUDED.ai_model,
                            ai_confidence = EXCLUDED.ai_confidence,
                            generated_at = EXCLUDED.generated_at,
                            updated_at = NOW()
                        WHERE capability_insights.status = 'pending'
                        -- Only update pending insights; fixed/auto_resolved/dismissed are preserved
                        """,
                        [
                            capability_type,
                            capability_id,
                            table_name,
                            insight_type,
                            severity,
                            finding,
                            expected_behavior,
                            actual_behavior,
                            impact,
                            suggested_fix,
                            reference_data,
                            self.model,
                            ai_confidence,
                            datetime.now(UTC),
                        ],
                    )

                conn.commit()

                logger.info("insights_saved", count=len(insights))

                return len(insights)

            except Exception as e:
                conn.rollback()
                logger.error("insights_save_failed", error=str(e))
                raise
