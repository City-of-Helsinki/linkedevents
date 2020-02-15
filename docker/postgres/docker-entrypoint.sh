#!/bin/bash

set -eo pipefail

source /docker-entrypoint-initdb.d/init-db.sh

init-db \
  "" \
  "" \
  "$POSTGRES_USER" \
  "$POSTGRES_PASSWORD" \
  "$MIGRATION_USER" \
  "$MIGRATION_PASSWORD" \
  "$APP_USER" \
  "$APP_PASSWORD" \
  "$POSTGRES_DB" \
  "false" \
  "true"
