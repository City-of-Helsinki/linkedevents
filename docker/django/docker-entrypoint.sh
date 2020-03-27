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

  CACHE_URL="redis://:${CACHE_PASSWORD}@${CACHE_HOST}/1"
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
    export DATABASE_URL=$APP_DATABASE_URL
    ./manage.py runserver "$RUNSERVER_ADDRESS"
  else
    echo 'Production application server here soon...'
  fi
fi

# As argument isn't `runserver`, assume user want to run his own process, for example a `bash`
# shell to explore this image
exec "$@"
