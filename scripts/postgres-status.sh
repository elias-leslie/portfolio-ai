#!/bin/bash
#
# PostgreSQL Status Monitoring Script
# Displays connection pool status, active queries, and database health
#
# Usage: ./scripts/postgres-status.sh

set -euo pipefail

# Configuration
DB_NAME="${DB_NAME:-portfolio_ai}"
DB_USER="${DB_USER:-portfolio_ai_user}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== PostgreSQL Status Monitor ===${NC}"
echo "Database: $DB_NAME"
echo "User: $DB_USER"
echo "Time: $(date)"
echo ""

# Check if PostgreSQL is running
if ! pg_isready -q; then
    echo -e "${RED}✗ PostgreSQL is not running${NC}"
    exit 1
fi

echo -e "${GREEN}✓ PostgreSQL is running${NC}"
echo ""

# Connection pool status
echo -e "${BLUE}Connection Pool Status:${NC}"
psql -U "$DB_USER" -d "$DB_NAME" -c "
SELECT
    state,
    count(*) as connections
FROM pg_stat_activity
WHERE datname = '$DB_NAME'
GROUP BY state
ORDER BY count(*) DESC;
" -t

echo ""

# Active queries
echo -e "${BLUE}Active Queries:${NC}"
ACTIVE_COUNT=$(psql -U "$DB_USER" -d "$DB_NAME" -t -c "
SELECT count(*) FROM pg_stat_activity
WHERE datname = '$DB_NAME' AND state = 'active' AND query NOT LIKE '%pg_stat_activity%';
")

if [ "$ACTIVE_COUNT" -gt 0 ]; then
    echo -e "${YELLOW}  Active queries: $ACTIVE_COUNT${NC}"
    psql -U "$DB_USER" -d "$DB_NAME" -c "
SELECT
    pid,
    usename,
    application_name,
    state,
    query_start,
    substring(query, 1, 50) as query
FROM pg_stat_activity
WHERE datname = '$DB_NAME'
  AND state = 'active'
  AND query NOT LIKE '%pg_stat_activity%'
ORDER BY query_start;
" -x
else
    echo -e "${GREEN}  No active queries${NC}"
fi

echo ""

# Database size
echo -e "${BLUE}Database Size:${NC}"
psql -U "$DB_USER" -d "$DB_NAME" -c "
SELECT
    pg_size_pretty(pg_database_size('$DB_NAME')) as size;
" -t

echo ""

# Table sizes
echo -e "${BLUE}Largest Tables:${NC}"
psql -U "$DB_USER" -d "$DB_NAME" -c "
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) AS indexes_size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;
"

echo ""

# Locks
LOCK_COUNT=$(psql -U "$DB_USER" -d "$DB_NAME" -t -c "
SELECT count(*) FROM pg_locks WHERE database = (SELECT oid FROM pg_database WHERE datname = '$DB_NAME');
")

if [ "$LOCK_COUNT" -gt 0 ]; then
    echo -e "${YELLOW}Active Locks: $LOCK_COUNT${NC}"
else
    echo -e "${GREEN}No active locks${NC}"
fi

echo ""
echo -e "${GREEN}✓ Status check complete${NC}"
