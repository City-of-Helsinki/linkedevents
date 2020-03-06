#!/bin/bash

set -eo pipefail

source /docker-entrypoint-initdb.d/init-db.sh

init-db \
  "" \
  "" \
  "$POSTGRES_USER" \
  "$POSTGRES_PASSWORD" \
  "$DB_MIGRATION_USER" \
  "$DB_MIGRATION_PASSWORD" \
  "$DB_APP_USER" \
  "$DB_APP_PASSWORD" \
  "$POSTGRES_DB" \
  "false" \
  "true"
