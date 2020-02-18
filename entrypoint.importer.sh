#!/bin/bash
# This file is used by Dockerfile.dist for running Linked Events importers

set -eo pipefail

# Require these env vars to be set
: "${APP_USER:?}"
: "${DB_HOST:?}"
: "${DB_NAME:?}"

# Makes it possible to fetch the app password from SSM instead of passing the password as an environment variable
# because AWS Batch doesn't support passing secrets and displays all environment variables as plain text
if [[ ! -z "$APP_PASSWORD_SSM_KEY" ]]; then
  APP_PASSWORD=$( \
    aws \
      ssm get-parameter \
      --name "$APP_PASSWORD_SSM_KEY" \
      --query 'Parameter.Value' \
      --with-decryption \
      --region eu-west-1 | tr -d '\"'
  )
  unset APP_PASSWORD_SSM_KEY
elif [[ -z "$APP_PASSWORD" ]]; then
  echo "APP_PASSWORD not set"
  exit 1
fi

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
