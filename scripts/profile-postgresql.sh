#!/bin/bash
# Profile PostgreSQL database usage
# Shows current connections, memory, cache performance, and query stats

set -e

echo "========================================"
echo "PostgreSQL Database Profile"
echo "========================================"
echo ""
echo "Timestamp: $(date)"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if we can connect
if ! sudo -u postgres psql -c "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${YELLOW}Note: Some queries require PostgreSQL access${NC}"
    echo "Run with: sudo bash $0"
    echo ""
fi

echo "===================="
echo "1. Connection Usage"
echo "===================="

sudo -u postgres psql -c "
SELECT
    max_conn,
    used,
    res_for_super,
    max_conn-used-res_for_super AS res_for_normal,
    ROUND(100.0 * used / max_conn, 2) AS pct_used
FROM
  (SELECT count(*) used FROM pg_stat_activity) t1,
  (SELECT setting::int res_for_super FROM pg_settings WHERE name='superuser_reserved_connections') t2,
  (SELECT setting::int max_conn FROM pg_settings WHERE name='max_connections') t3;
" 2>/dev/null || echo "Could not query connection stats"

echo ""
echo "Active connections by state:"
sudo -u postgres psql -c "
SELECT
    state,
    count(*) as connections,
    ROUND(100.0 * count(*) / sum(count(*)) OVER (), 2) as pct
FROM pg_stat_activity
WHERE state IS NOT NULL
GROUP BY state
ORDER BY connections DESC;
" 2>/dev/null || echo "Could not query connection states"

echo ""
echo "Connections by database:"
sudo -u postgres psql -c "
SELECT
    datname,
    count(*) as connections
FROM pg_stat_activity
WHERE datname IS NOT NULL
GROUP BY datname
ORDER BY connections DESC;
" 2>/dev/null || echo "Could not query database connections"

echo ""
echo "========================"
echo "2. Memory & Cache Stats"
echo "========================"

sudo -u postgres psql -c "
SELECT
    name,
    setting,
    unit,
    context
FROM pg_settings
WHERE name IN (
    'shared_buffers',
    'effective_cache_size',
    'maintenance_work_mem',
    'work_mem',
    'max_connections'
)
ORDER BY name;
" 2>/dev/null || echo "Could not query memory settings"

echo ""
echo "Buffer cache hit ratio (target: >95%):"
sudo -u postgres psql -c "
SELECT
    ROUND(100.0 * sum(heap_blks_hit) / NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0), 2) as cache_hit_ratio_pct,
    sum(heap_blks_hit) as heap_hits,
    sum(heap_blks_read) as heap_reads
FROM pg_statio_user_tables;
" 2>/dev/null || echo "Could not query cache hit ratio"

echo ""
echo "============================"
echo "3. Database Size & Activity"
echo "============================"

sudo -u postgres psql -c "
SELECT
    datname,
    pg_size_pretty(pg_database_size(datname)) as size,
    numbackends as active_conns
FROM pg_stat_database
WHERE datname NOT IN ('template0', 'template1', 'postgres')
ORDER BY pg_database_size(datname) DESC;
" 2>/dev/null || echo "Could not query database sizes"

echo ""
echo "Table sizes (top 10):"
sudo -u postgres psql -d portfolio_ai -c "
SELECT
    schemaname || '.' || tablename as table,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as index_size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;
" 2>/dev/null || echo "Could not query table sizes"

echo ""
echo "====================="
echo "4. Query Performance"
echo "====================="

# Check if pg_stat_statements is available
if sudo -u postgres psql -c "SELECT 1 FROM pg_extension WHERE extname='pg_stat_statements';" 2>/dev/null | grep -q 1; then
    echo "Top 10 slowest queries:"
    sudo -u postgres psql -d portfolio_ai -c "
    SELECT
        ROUND(total_exec_time::numeric, 2) as total_ms,
        calls,
        ROUND(mean_exec_time::numeric, 2) as mean_ms,
        ROUND(max_exec_time::numeric, 2) as max_ms,
        LEFT(query, 80) as query_snippet
    FROM pg_stat_statements
    ORDER BY total_exec_time DESC
    LIMIT 10;
    " 2>/dev/null || echo "Could not query pg_stat_statements"
else
    echo "pg_stat_statements extension not installed (optional)"
    echo "To enable: sudo -u postgres psql -c \"CREATE EXTENSION pg_stat_statements;\""
fi

echo ""
echo "============================="
echo "5. Lock & Wait Event Analysis"
echo "============================="

sudo -u postgres psql -c "
SELECT
    wait_event_type,
    wait_event,
    count(*) as count
FROM pg_stat_activity
WHERE wait_event IS NOT NULL
GROUP BY wait_event_type, wait_event
ORDER BY count DESC
LIMIT 10;
" 2>/dev/null || echo "Could not query wait events"

echo ""
echo "Current locks:"
sudo -u postgres psql -c "
SELECT
    locktype,
    mode,
    count(*) as count
FROM pg_locks
GROUP BY locktype, mode
ORDER BY count DESC;
" 2>/dev/null || echo "Could not query locks"

echo ""
echo "========================"
echo "6. Replication & WAL"
echo "========================"

sudo -u postgres psql -c "
SELECT
    pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), '0/0')) as wal_written,
    count(*) as wal_files
FROM pg_ls_waldir();
" 2>/dev/null || echo "Could not query WAL stats"

echo ""
echo "============================="
echo "7. System Resource Consumption"
echo "============================="

echo "PostgreSQL process memory:"
ps aux | grep postgres | grep -v grep | awk '{sum+=$6} END {print "Total: " sum/1024 " MB"}'

echo ""
echo "PostgreSQL process count:"
ps aux | grep postgres | grep -v grep | wc -l

echo ""
echo "============================="
echo "8. Recommendations"
echo "============================="

# Analyze and provide recommendations
CONNECTIONS=$(sudo -u postgres psql -t -c "SELECT count(*) FROM pg_stat_activity;" 2>/dev/null | tr -d ' ')
MAX_CONN=$(sudo -u postgres psql -t -c "SELECT setting::int FROM pg_settings WHERE name='max_connections';" 2>/dev/null | tr -d ' ')
SHARED_BUF=$(sudo -u postgres psql -t -c "SELECT setting FROM pg_settings WHERE name='shared_buffers';" 2>/dev/null | tr -d ' ')

echo ""
if [ ! -z "$CONNECTIONS" ] && [ ! -z "$MAX_CONN" ]; then
    PCT_USED=$((100 * CONNECTIONS / MAX_CONN))
    echo "Connection usage: $CONNECTIONS / $MAX_CONN ($PCT_USED%)"

    if [ $PCT_USED -gt 80 ]; then
        echo -e "${YELLOW}⚠ WARNING: Connection usage >80%${NC}"
        echo "  Recommendation: Increase max_connections or reduce pool sizes"
    elif [ $PCT_USED -lt 20 ]; then
        echo -e "${GREEN}✓ Connection usage is healthy (<20%)${NC}"
    else
        echo -e "${GREEN}✓ Connection usage is acceptable${NC}"
    fi
fi

echo ""
echo "For detailed monitoring, consider:"
echo "  • Install pg_stat_statements extension for query insights"
echo "  • Enable log_min_duration_statement for slow query logging"
echo "  • Monitor cache hit ratio daily (should stay >95%)"
echo ""
echo "Profile complete!"
