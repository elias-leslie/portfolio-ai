#!/bin/sh
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
  SELECT 'CREATE DATABASE portfolio_ai'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'portfolio_ai')\gexec
  SELECT 'CREATE DATABASE hatchet'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'hatchet')\gexec
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname portfolio_ai \
  <<-EOSQL
  CREATE EXTENSION IF NOT EXISTS vector;
  CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
EOSQL
