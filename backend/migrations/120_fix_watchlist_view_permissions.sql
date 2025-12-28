-- Migration 120: Fix watchlist_snapshots_v view permissions
--
-- Issue: The view watchlist_snapshots_v is owned by portfolio_ai_user but
-- references tables owned by portfolio_app. PostgreSQL views execute with
-- the view owner's permissions, causing "permission denied" errors.
--
-- Root cause: Tables were created by portfolio_app after schema split (migration 070),
-- but the view was created earlier by portfolio_ai_user.
--
-- Impact: Blocked both API reads and Celery task writes until fixed.

-- Grant SELECT on watchlist split tables to portfolio_ai_user (view owner)
GRANT SELECT ON watchlist_snapshots_core TO portfolio_ai_user;
GRANT SELECT ON watchlist_technical_metrics TO portfolio_ai_user;
GRANT SELECT ON watchlist_narrative TO portfolio_ai_user;
GRANT SELECT ON watchlist_news_summary TO portfolio_ai_user;

-- Also grant on base table to ensure future compatibility
GRANT SELECT ON watchlist_items TO portfolio_ai_user;
GRANT SELECT ON watchlist_snapshots TO portfolio_ai_user;
