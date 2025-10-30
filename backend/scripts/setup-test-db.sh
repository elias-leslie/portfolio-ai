#!/bin/bash
# Setup test database for Portfolio AI Platform
#
# This script creates a separate test database to prevent tests from
# cleaning production data.
#
# Run with: sudo bash scripts/setup-test-db.sh

set -e

echo "Creating test database..."

sudo -u postgres psql <<EOF
-- Create test database if it doesn't exist
SELECT 'CREATE DATABASE portfolio_ai_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'portfolio_ai_test')\gexec

-- Grant privileges to portfolio_ai_user
GRANT ALL PRIVILEGES ON DATABASE portfolio_ai_test TO portfolio_ai_user;

\c portfolio_ai_test

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO portfolio_ai_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO portfolio_ai_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO portfolio_ai_user;

EOF

echo "✅ Test database created: portfolio_ai_test"
echo ""
echo "The test database will be automatically used when running tests."
echo "To manually use it, set: export TEST_DATABASE_URL=postgresql://portfolio_ai_user:REDACTED_PASSWORD@localhost:5432/portfolio_ai_test"
