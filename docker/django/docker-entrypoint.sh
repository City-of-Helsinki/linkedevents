#!/bin/bash

set -euo pipefail

if [[ "$WAIT_FOR_IT_ADDRESS" ]]; then
    wait-for-it.sh "$WAIT_FOR_IT_ADDRESS" --timeout=30
fi

if [[ $# -lt 1 ]] || [[ "$1" == "runserver" ]]; then
  # Require these env vars to be set
  : "${CACHE_HOST:?}"
  : "${CACHE_PASSWORD:?}"
  : "${DB_APP_PASSWORD:?}"
  : "${DB_APP_USER:?}"
  : "${DB_HOST:?}"
  : "${DB_MIGRATION_PASSWORD:?}"
  : "${DB_MIGRATION_USER:?}"
  : "${DB_NAME:?}"

  CACHE_DB="${CACHE_DB:-"1"}"
  # Use the same cache DB for the ongoing_local cache if the cache DB isn't explicitly defined
  ONGOING_LOCAL_CACHE_DB="${ONGOING_LOCAL_CACHE_DB:-$CACHE_DB}"

  # Redis doesn't provide TSL by default and the local Redis container doesn't have any extra configuration for setting
  # up TSL so we use Redis without TSL in the local environment
  CACHE_URL="redis://:${CACHE_PASSWORD}@${CACHE_HOST}/${CACHE_DB}"
  ONGOING_LOCAL_CACHE_URL="redis://:${CACHE_PASSWORD}@${CACHE_HOST}/${ONGOING_LOCAL_CACHE_DB}"
  APP_DATABASE_URL="postgis://${DB_APP_USER}:${DB_APP_PASSWORD}@${DB_HOST}/${DB_NAME}"
  MIGRATION_DATABASE_URL="postgis://${DB_MIGRATION_USER}:${DB_MIGRATION_PASSWORD}@${DB_HOST}/${DB_NAME}"

  if [[ "$APPLY_MIGRATIONS" = "true" ]]; then
    echo "Applying database migrations..."
    DATABASE_URL=$MIGRATION_DATABASE_URL ./manage.py migrate --noinput
    echo "Applying sync_translation_fields migrations..."
    DATABASE_URL=$MIGRATION_DATABASE_URL ./manage.py sync_translation_fields --noinput
  fi

  if [[ "$CREATE_SUPERUSER" = "true" ]]; then
    DATABASE_URL=$APP_DATABASE_URL ./manage.py create_admin_superuser
  fi

  if [[ "$DEV_SERVER" = "true" ]]; then
    export CACHE_URL
    export ONGOING_LOCAL_CACHE_URL
    export DATABASE_URL=$APP_DATABASE_URL
    ./manage.py runserver "$RUNSERVER_ADDRESS"
  else
    echo 'Production application server here soon...'
  fi
fi

# As argument isn't `runserver`, assume user want to run his own process, for example a `bash`
# shell to explore this image
exec "$@"
