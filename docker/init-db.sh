#!/bin/sh
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
  SELECT 'CREATE DATABASE portfolio_ai'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'portfolio_ai')\gexec
  SELECT 'CREATE DATABASE hatchet'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'hatchet')\gexec
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname portfolio_ai \
  -f /docker-bootstrap/portfolio-ai-schema.sql

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname portfolio_ai <<-EOSQL
  INSERT INTO alembic_version (version_num)
  SELECT 'b3d9e1c4a7f2'
  WHERE NOT EXISTS (SELECT 1 FROM alembic_version);
EOSQL
