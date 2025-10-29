#!/bin/bash
# Validate API keys and check quota limits for watchlist data sources
# Usage: ./scripts/validate-api-quotas.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "================================"
echo "API Quota Validation"
echo "================================"
echo ""

# Load environment variables (if .env exists)
if [ -f "$PROJECT_ROOT/backend/.env" ]; then
    set -a
    source "$PROJECT_ROOT/backend/.env"
    set +a
    echo "Loaded API keys from backend/.env"
    echo ""
else
    echo "No .env file found - checking system environment variables"
    echo ""
fi

# Track validation results
TOTAL_SOURCES=0
VALID_SOURCES=0
INVALID_SOURCES=0
QUOTA_WARNINGS=0

# Function to check if an API key is set (database or environment)
check_api_key() {
    local key_name=$1
    local source_id=$2

    # Check database first (if project is running)
    if command -v python3 &> /dev/null && [ -f "$PROJECT_ROOT/backend/app/storage/__init__.py" ]; then
        DB_CHECK=$(cd "$PROJECT_ROOT/backend" && python3 -c "
import os, sys
sys.path.insert(0, '.')
try:
    from app.storage import get_storage
    storage = get_storage()
    df = storage.query(\"SELECT value FROM source_credentials WHERE source_id = ? AND field = 'apikey'\", ['$source_id'])
    if not df.is_empty():
        value = df.to_dicts()[0]['value']
        if value and value not in ('your_key_here', 'PLACEHOLDER'):
            print('configured')
            sys.exit(0)
except:
    pass
print('not_configured')
" 2>/dev/null)

        if [ "$DB_CHECK" = "configured" ]; then
            return 0
        fi
    fi

    # Fall back to environment variable
    local key_value="${!key_name:-}"

    if [ -z "$key_value" ] || [ "$key_value" = "your_key_here" ] || [ "$key_value" = "PLACEHOLDER" ]; then
        return 1
    fi
    return 0
}

# Function to validate a source
validate_source() {
    local source_name=$1
    local source_id=$2
    local key_var=$3
    local quota_info=$4

    TOTAL_SOURCES=$((TOTAL_SOURCES + 1))

    echo -e "${BLUE}Checking $source_name...${NC}"

    if check_api_key "$key_var" "$source_id"; then
        echo -e "  ${GREEN}✓${NC} API key configured"
        echo -e "  ${BLUE}ℹ${NC} Quota: $quota_info"
        VALID_SOURCES=$((VALID_SOURCES + 1))
    else
        echo -e "  ${YELLOW}⚠${NC} API key not configured (database or $key_var)"
        INVALID_SOURCES=$((INVALID_SOURCES + 1))
    fi
    echo ""
}

echo "Validating API keys..."
echo ""

# Validate each data source (name, source_id, env_var, quota_info)
validate_source "YFinance" "yfinance" "YFINANCE_KEY" "Unlimited (free tier)"
validate_source "TwelveData" "twelvedata" "TWELVEDATA_API_KEY" "8 req/min, 800/day"
validate_source "FMP" "fmp" "FMP_API_KEY" "~250/day (estimated)"
validate_source "Polygon" "polygon" "POLYGON_API_KEY" "5 req/min, 7200/day"
validate_source "Finnhub" "finnhub" "FINNHUB_API_KEY" "60 req/min, unlimited/day"
validate_source "NewsAPI" "newsapi" "NEWSAPI_KEY" "100/day"
validate_source "Alpha Vantage" "alphavantage" "ALPHAVANTAGE_API_KEY" "25 req/day (free tier)"
validate_source "FRED" "fred" "FRED_API_KEY" "Unlimited (free tier)"

echo "================================"
echo "Summary"
echo "================================"
echo ""
echo "Total sources checked: $TOTAL_SOURCES"
echo -e "${GREEN}Valid API keys: $VALID_SOURCES${NC}"
if [ $INVALID_SOURCES -gt 0 ]; then
    echo -e "${YELLOW}Missing/Invalid keys: $INVALID_SOURCES${NC}"
fi
echo ""

# Calculate safe watchlist size based on available sources
if [ $VALID_SOURCES -ge 3 ]; then
    echo -e "${GREEN}✓ Sufficient data sources for watchlist feature${NC}"
    echo ""
    echo "Safe watchlist size recommendations:"
    echo "  - With YFinance only: 100+ tickers (unlimited)"
    echo "  - With TwelveData: ~50 tickers (15-min refresh)"
    echo "  - With all sources: 100+ tickers (failover redundancy)"
    echo ""
    echo "Recommended configuration:"
    echo "  - Refresh interval: 15 minutes"
    echo "  - Max tickers: 50 (conservative)"
    echo "  - Batching: Enabled"
    EXIT_CODE=0
elif [ $VALID_SOURCES -ge 1 ]; then
    echo -e "${YELLOW}⚠ Limited data sources available${NC}"
    echo "  Recommendation: Add more API keys for failover redundancy"
    echo "  Minimum viable: 1 source (YFinance)"
    echo "  Safe watchlist size: 20-30 tickers"
    EXIT_CODE=0
else
    echo -e "${RED}✗ No valid data sources configured${NC}"
    echo "  Action required: Configure at least one API key"
    echo "  Primary source: YFinance (no key required)"
    EXIT_CODE=1
fi

echo ""
echo "For more details, see: docs/core/OPERATIONS.md"
echo ""

exit $EXIT_CODE
