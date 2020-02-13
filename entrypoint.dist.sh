#!/bin/bash
# This file is used by Dockerfile.dist

set -euo pipefail

# Require these env vars to be set
: "${APP_DATABASE_URL:?}"
: "${MIGRATION_DATABASE_URL:?}"
: "${SECRET_KEY:?}"
: "${TOKEN_AUTH_ACCEPTED_AUDIENCE:?}"
: "${TOKEN_AUTH_SHARED_SECRET:?}"

# if the first argument to `docker run` starts with `--`, the user is passing gunicorn arguments
if [[ $# -lt 1 ]] || [[ "$1" == "--"* ]]; then
    # Check Django configuration for issues
    python manage.py check --deploy

    # Run migrations
    DATABASE_URL=$MIGRATION_DATABASE_URL ./manage.py migrate --noinput
    unset MIGRATION_DATABASE_URL

    export DATABASE_URL=$APP_DATABASE_URL
    unset APP_DATABASE_URL

    # Run as exec so the application can receive any Unix signals sent to the container, e.g., Ctrl + C.
    # Bind to 0.0.0.0 (listen to all network interfaces) so that it's possible to access from the outside
    exec gunicorn linkedevents.wsgi --timeout 600 --workers=4 --bind 0.0.0.0:8000 "$@"
fi

# As argument is not --env, assume user want to run his own process, for sample a `bash`
# shell to explore this image
exec "$@"
