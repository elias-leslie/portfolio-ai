#!/bin/bash
# Populate source_credentials table with API keys from environment variables
# Usage: ./scripts/seed-api-keys.sh

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
echo "Seeding API Keys to Database"
echo "================================"
echo ""

# Activate venv
if [ ! -d "$PROJECT_ROOT/backend/.venv" ]; then
    echo -e "${RED}ERROR: Virtual environment not found at backend/.venv${NC}"
    exit 1
fi

cd "$PROJECT_ROOT/backend"
source .venv/bin/activate

# Run Python script to seed keys
python3 << 'EOF'
import os
import sys
from app.storage import get_storage

# Source mapping: source_id -> environment variable name
SOURCES = {
    "yfinance": "YFINANCE_KEY",
    "twelvedata": "TWELVEDATA_API_KEY",
    "fmp": "FMP_API_KEY",
    "polygon": "POLYGON_API_KEY",
    "finnhub": "FINNHUB_API_KEY",
    "newsapi": "NEWSAPI_KEY",
    "alphavantage": "ALPHAVANTAGE_API_KEY",
    "fred": "FRED_API_KEY",
}

try:
    storage = get_storage()
    seeded = 0
    skipped = 0

    for source_id, env_var in SOURCES.items():
        api_key = os.getenv(env_var)

        if not api_key or api_key in ("your_key_here", "PLACEHOLDER"):
            print(f"⚠ Skipping {source_id}: {env_var} not set in environment")
            skipped += 1
            continue

        # Insert or update in database
        storage.query(
            """
            INSERT INTO source_credentials (source_id, field, value)
            VALUES (?, 'apikey', ?)
            ON CONFLICT (source_id, field) DO UPDATE SET
                value = EXCLUDED.value,
                updated_at = now()
            """,
            [source_id, api_key]
        )

        print(f"✓ Seeded {source_id} API key from {env_var}")
        seeded += 1

    print("")
    print(f"Summary: {seeded} keys seeded, {skipped} skipped")

    if seeded > 0:
        sys.exit(0)
    else:
        print("⚠ No API keys were seeded. Make sure environment variables are set.")
        sys.exit(1)

except Exception as e:
    print(f"ERROR: Failed to seed API keys: {e}")
    sys.exit(1)
EOF

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ API keys successfully seeded to database${NC}"
else
    echo -e "${YELLOW}⚠ Some API keys were not seeded (see above)${NC}"
fi

exit $EXIT_CODE
