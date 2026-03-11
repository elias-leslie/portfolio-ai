#!/bin/bash
# Setup test database for Portfolio AI Platform
#
# This script creates a separate test database to prevent tests from
# cleaning production data.
#
# Run with: sudo bash scripts/setup-test-db.sh

set -e

if [[ -z "${POSTGRES_ADMIN_URL:-}" && -f "$HOME/.env.local" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$HOME/.env.local"
  set +a
fi

if [[ -n "${POSTGRES_ADMIN_URL:-}" ]]; then
  PSQL_CMD=(psql "$POSTGRES_ADMIN_URL")
else
  PSQL_CMD=(sudo -u postgres psql)
fi

echo "Creating test database..."

"${PSQL_CMD[@]}" <<EOF
-- Create test database if it doesn't exist
SELECT 'CREATE DATABASE portfolio_ai_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'portfolio_ai_test')\gexec

-- Keep the test database owned by the role that runs migrations in tests.
ALTER DATABASE portfolio_ai_test OWNER TO portfolio_app;
GRANT ALL PRIVILEGES ON DATABASE portfolio_ai_test TO portfolio_app;

\c portfolio_ai_test

ALTER SCHEMA public OWNER TO portfolio_app;

DO \$\$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'portfolio_ai_user') THEN
        EXECUTE 'REASSIGN OWNED BY portfolio_ai_user TO portfolio_app';
    END IF;
END
\$\$;

-- Grant schema privileges after ownership repair so reruns are idempotent.
GRANT ALL ON SCHEMA public TO portfolio_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO portfolio_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO portfolio_app;

EOF

echo "✅ Test database created: portfolio_ai_test"
echo ""
echo "The test database will be automatically used when running tests."
echo "Existing legacy objects are reassigned to portfolio_app on each run."
echo "To manually use it, set: export TEST_DATABASE_URL=postgresql://portfolio_app:$PGPASSWORD@localhost:5432/portfolio_ai_test"
