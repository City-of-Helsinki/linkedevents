#!/bin/bash
# This file is used by Dockerfile.dist for running Linked Events importers

set -euo pipefail

# Require these env vars to be set
: "${APP_PASSWORD:?}"
: "${APP_USER:?}"
: "${DB_HOST:?}"
: "${DB_NAME:?}"

APP_DATABASE_URL="postgis://${APP_USER}:${APP_PASSWORD}@${DB_HOST}/${DB_NAME}"
unset APP_PASSWORD
unset APP_USER

# If the first argument to `docker run` starts with any of the import commands
if [[ $# -lt 1 ]] || [[ "$1" == "event_import" || "$1" == "install_templates"  || "$1" == "geo_import" ]]; then
  export DATABASE_URL=$APP_DATABASE_URL
  unset APP_DATABASE_URL

  # Run as exec so the application can receive any Unix signals sent to the container, e.g., Ctrl + C.
  exec python manage.py "$@"
fi

# As argument is not any of the import commands, assume user wants to run his own process, for example a `bash`
# shell to explore this image
exec "$@"
