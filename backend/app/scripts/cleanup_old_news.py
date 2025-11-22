#!/usr/bin/env python3
"""Cleanup old news articles from the database.

This script removes news articles older than a specified number of days
to manage database size and improve query performance.

Usage:
    python -m app.scripts.cleanup_old_news --dry-run
    python -m app.scripts.cleanup_old_news --days 90
    python -m app.scripts.cleanup_old_news --days 30 --verbose
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# Add parent directory to path for imports when run as script
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.logging_config import get_logger
from app.storage.connection import get_connection_manager

logger = get_logger(__name__)


def cleanup_old_news(days: int = 90, dry_run: bool = True) -> dict[str, Any]:
    """Delete news articles older than specified days.

    Args:
        days: Number of days to keep (delete older articles)
        dry_run: If True, only count articles without deleting

    Returns:
        Dict with summary: deleted count, date range, dry_run flag
    """
    cutoff_date = datetime.now(UTC) - timedelta(days=days)

    logger.info(
        "cleanup_old_news_started",
        days=days,
        cutoff_date=cutoff_date.isoformat(),
        dry_run=dry_run,
    )

    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # First, find the date range of articles to be deleted
            result = conn.execute(
                """
                SELECT
                    MIN(published_at) as oldest,
                    MAX(published_at) as newest,
                    COUNT(*) as count
                FROM news_headlines
                WHERE published_at < ?
                """,
                [cutoff_date],
            ).fetchone()

            if not result or (
                result[2] is not None and isinstance(result[2], int) and result[2] == 0
            ):
                logger.info("cleanup_old_news_no_articles", cutoff_date=cutoff_date.isoformat())
                return {
                    "deleted": 0,
                    "dry_run": dry_run,
                    "cutoff_date": cutoff_date.isoformat(),
                    "oldest_date": None,
                    "newest_date": None,
                }

            oldest_date = result[0]
            newest_date = result[1]
            count = result[2]

            logger.info(
                "cleanup_old_news_found_articles",
                count=count,
                oldest=oldest_date,
                newest=newest_date,
            )

            if not dry_run:
                # Delete articles older than cutoff date
                conn.execute(
                    """
                    DELETE FROM news_headlines
                    WHERE published_at < ?
                    """,
                    [cutoff_date],
                )
                conn.commit()
                logger.info("cleanup_old_news_deleted", count=count)
            else:
                logger.info("cleanup_old_news_dry_run", count=count)

            summary = {
                "deleted": count,
                "dry_run": dry_run,
                "cutoff_date": cutoff_date.isoformat(),
                "oldest_date": oldest_date.isoformat()
                if isinstance(oldest_date, datetime)
                else None,
                "newest_date": newest_date.isoformat()
                if isinstance(newest_date, datetime)
                else None,
            }

            logger.info("cleanup_old_news_completed", summary=summary)
            return summary

    except Exception as e:
        logger.error("cleanup_old_news_error", error=str(e), exc_info=True)
        raise


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Clean up old news articles from database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview what would be deleted (dry-run mode)
  python -m app.scripts.cleanup_old_news --dry-run --days 90

  # Actually delete articles older than 90 days
  python -m app.scripts.cleanup_old_news --days 90

  # Delete articles older than 30 days
  python -m app.scripts.cleanup_old_news --days 30
        """,
    )

    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Delete news older than this many days (default: 90)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview what would be deleted without actually deleting",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    try:
        result = cleanup_old_news(days=args.days, dry_run=args.dry_run)

        # Print JSON summary to stdout for programmatic use
        print(json.dumps(result, indent=2))

        return 0

    except Exception as e:
        logger.error("cleanup_script_failed", error=str(e), exc_info=True)
        print(json.dumps({"error": str(e)}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
