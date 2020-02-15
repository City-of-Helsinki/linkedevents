#!/bin/bash

set -euo pipefail

# Require these env vars to be set
: "${APP_PASSWORD:?}"
: "${APP_USER:?}"
: "${DB_HOST:?}"
: "${DB_NAME:?}"
: "${MIGRATION_PASSWORD:?}"
: "${MIGRATION_USER:?}"

APP_DATABASE_URL="postgis://${APP_USER}:${APP_PASSWORD}@${DB_HOST}/${DB_NAME}"
MIGRATION_DATABASE_URL="postgis://${MIGRATION_USER}:${MIGRATION_PASSWORD}@${DB_HOST}/${DB_NAME}"

if [[ "$WAIT_FOR_IT_ADDRESS" ]]; then
    wait-for-it.sh "$WAIT_FOR_IT_ADDRESS" --timeout=30
fi

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
    DATABASE_URL=$APP_DATABASE_URL ./manage.py runserver "$RUNSERVER_ADDRESS"
else
    echo 'Production application server here soon...'
fi
