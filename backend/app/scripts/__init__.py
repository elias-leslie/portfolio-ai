"""Maintenance CLI scripts for portfolio-ai.

This package contains standalone maintenance scripts for:
- Database cleanup (removing old data)
- Database optimization (VACUUM ANALYZE)
- Data integrity validation (orphaned records, FK consistency)

All scripts support:
- --dry-run flag for safe preview
- Structured logging with get_logger()
- JSON output for programmatic use
- Standalone CLI execution
"""
