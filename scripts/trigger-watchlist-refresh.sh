#!/usr/bin/env bash
# Manually trigger watchlist data refresh (for testing and manual runs)
#
# This script:
# 1. Gets all watchlist tickers from the database
# 2. Triggers historical OHLCV data ingestion (200 days for initial, 5 for refresh)
# 3. Calculates technical indicators
# 4. Refreshes watchlist scores
#
# Usage:
#   ./scripts/trigger-watchlist-refresh.sh [--initial]
#
# Options:
#   --initial  - Fetch 200 days of data (first run), default is 5 days (refresh)

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Parse arguments
DAYS=5
if [[ "${1:-}" == "--initial" ]]; then
    DAYS=200
    echo -e "${YELLOW}Running INITIAL data fetch (200 days)${NC}"
else
    echo -e "${YELLOW}Running refresh (5 days)${NC}"
fi

# Change to backend directory
cd "$(dirname "$0")/../backend"

# Activate virtual environment
if [[ ! -f ".venv/bin/activate" ]]; then
    echo -e "${RED}Error: Virtual environment not found at .venv/${NC}"
    exit 1
fi

source .venv/bin/activate

echo -e "${GREEN}[1/4] Fetching watchlist tickers from database...${NC}"
TICKERS=$(python3 -c "
import sys
import logging
logging.disable(logging.CRITICAL)  # Suppress all logging output
from app.storage import get_storage
storage = get_storage()
result = storage.query('SELECT DISTINCT symbol FROM watchlist_items')
tickers = [row[0] for row in result]
sys.stdout.write(','.join(tickers))
" 2>/dev/null)

if [[ -z "$TICKERS" ]]; then
    echo -e "${RED}No tickers found in watchlist. Please add tickers first.${NC}"
    exit 1
fi

echo -e "${GREEN}Found tickers: ${TICKERS}${NC}"
TICKER_ARRAY=(${TICKERS//,/ })
TICKER_COUNT=${#TICKER_ARRAY[@]}

echo -e "${GREEN}[2/4] Triggering historical OHLCV data ingestion (${DAYS} days, ${TICKER_COUNT} tickers)...${NC}"
python3 -c "
from app.tasks.agent_tasks import ingest_historical_ohlcv
result = ingest_historical_ohlcv.delay(tickers=['${TICKERS//,/\',\'}'], days=${DAYS})
print(f'Task ID: {result.id}')
print('Background task queued. Check Celery worker logs for progress.')
"

echo -e "${GREEN}Waiting 30 seconds for data ingestion to complete...${NC}"
sleep 30

echo -e "${GREEN}[3/4] Triggering technical indicators calculation...${NC}"
python3 -c "
from app.tasks.agent_tasks import update_technical_indicators
result = update_technical_indicators.delay(tickers=['${TICKERS//,/\',\'}'])
print(f'Task ID: {result.id}')
print('Background task queued. Check Celery worker logs for progress.')
"

echo -e "${GREEN}Waiting 20 seconds for indicators to calculate...${NC}"
sleep 20

echo -e "${GREEN}[4/4] Refreshing watchlist scores...${NC}"
python3 -c "
from app.tasks.agent_tasks import refresh_watchlist_scores_task
result = refresh_watchlist_scores_task.delay(account_id=None)
print(f'Task ID: {result.id}')
print('Background task queued. Check Celery worker logs for progress.')
"

echo -e "${GREEN}Waiting 10 seconds for scores to refresh...${NC}"
sleep 10

echo -e "${GREEN}[DONE] Verifying results...${NC}"
python3 -c "
from app.storage import get_storage
storage = get_storage()

# Check day_bars
bars_result = storage.query('SELECT COUNT(*) as count FROM day_bars')
bars_count = bars_result[0][0]
print(f'Historical bars in database: {bars_count}')

# Check technical_indicators
indicators_result = storage.query('SELECT COUNT(*) as count FROM technical_indicators')
indicators_count = indicators_result[0][0]
print(f'Technical indicators calculated: {indicators_count}')

# Check watchlist scores
scores_result = storage.query('''
    SELECT
        wi.symbol,
        ROUND(ws.fundamental_score, 2) as price,
        ROUND(ws.technical_score, 2) as technical,
        ROUND(ws.overall_score, 2) as overall
    FROM watchlist_items wi
    LEFT JOIN watchlist_snapshots ws ON wi.id = ws.item_id
    ORDER BY wi.symbol
''')

print('\nWatchlist Scores:')
print('-' * 60)
print(f\"{'Ticker':<10} {'Price':<10} {'Technical':<12} {'Overall':<10}\")
print('-' * 60)
for row in scores_result:
    symbol, price, technical, overall = row
    print(f'{symbol:<10} {price or 0:<10} {technical or 0:<12} {overall or 0:<10}')
print('-' * 60)
"

echo -e "${GREEN}✓ Watchlist data refresh complete!${NC}"
echo -e "${YELLOW}Note: If scores are still 0, check Celery worker logs for errors.${NC}"
echo -e "${YELLOW}Make sure Redis and Celery worker are running.${NC}"
