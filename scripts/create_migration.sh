#!/bin/bash
# Create a new database migration file
# Usage: ./scripts/create_migration.sh "description_of_migration"

set -e

# Check if description is provided
if [ -z "$1" ]; then
    echo "Error: Migration description required"
    echo "Usage: $0 \"description_of_migration\""
    echo "Example: $0 \"add_user_email_column\""
    exit 1
fi

DESCRIPTION="$1"
MIGRATIONS_DIR="backend/migrations"

# Create migrations directory if it doesn't exist
mkdir -p "$MIGRATIONS_DIR"

# Find the last migration number
LAST_MIGRATION=$(ls -1 "$MIGRATIONS_DIR"/*.sql 2>/dev/null | sort -V | tail -n 1)

if [ -z "$LAST_MIGRATION" ]; then
    # No migrations exist yet
    NEXT_VERSION="001"
else
    # Extract version number and increment
    LAST_VERSION=$(basename "$LAST_MIGRATION" | cut -d'_' -f1)
    NEXT_VERSION=$(printf "%03d" $((10#$LAST_VERSION + 1)))
fi

# Create migration filename
FILENAME="${MIGRATIONS_DIR}/${NEXT_VERSION}_${DESCRIPTION}.sql"

# Create migration file with template
cat > "$FILENAME" << EOF
-- Migration: ${NEXT_VERSION}_${DESCRIPTION}
-- Description: ${DESCRIPTION}
-- Created: $(date +"%Y-%m-%d %H:%M:%S")

-- Add your SQL migration statements below
-- Example:
-- ALTER TABLE portfolio_positions ADD COLUMN IF NOT EXISTS notes TEXT;

-- Your migration SQL here:

EOF

echo "Created migration: $FILENAME"
echo ""
echo "Next steps:"
echo "1. Edit $FILENAME and add your SQL migration statements"
echo "2. Test the migration by restarting the backend"
echo "3. Commit the migration file to version control"
