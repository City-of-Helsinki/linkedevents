#!/bin/bash
# This file is used by Dockerfile.dist for running administrative tasks

set -eo pipefail

# Require these env vars to be set
: "${DB_APP_USER:?}"
: "${DB_HOST:?}"
: "${DB_NAME:?}"

CACHE_TLS="${CACHE_TLS:-true}"
ONGOING_LOCAL_CACHE_DB="${ONGOING_LOCAL_CACHE_DB:-"1"}"

# Makes it possible to fetch the app passwords from SSM instead of passing the passwords as environment variables
# because AWS Batch doesn't support passing secrets and displays all environment variables as plain text
if [[ -n "$CACHE_PASSWORD_SSM_KEY" ]]; then
  CACHE_PASSWORD=$( \
    aws \
      ssm get-parameter \
      --name "$CACHE_PASSWORD_SSM_KEY" \
      --query 'Parameter.Value' \
      --with-decryption \
      --region eu-west-1 | tr -d '\"'
  )
  unset CACHE_PASSWORD_SSM_KEY
elif [[ -z "$CACHE_PASSWORD" ]]; then
  echo "CACHE_PASSWORD not set"
fi

if [[ -n "$DB_APP_PASSWORD_SSM_KEY" ]]; then
  DB_APP_PASSWORD=$( \
    aws \
      ssm get-parameter \
      --name "$DB_APP_PASSWORD_SSM_KEY" \
      --query 'Parameter.Value' \
      --with-decryption \
      --region eu-west-1 | tr -d '\"'
  )
  unset DB_APP_PASSWORD_SSM_KEY
elif [[ -z "$DB_APP_PASSWORD" ]]; then
  echo "DB_APP_PASSWORD not set"
  exit 1
fi

# The ONGOING_LOCAL_CACHE_URL is currently only used by the populate_local_event_cache management command so that's why
# it's optional and only set if CACHE_PASSWORD and CACHE_HOST are set
if [[ -n "$CACHE_PASSWORD" && -n "$CACHE_HOST" ]]; then

  # Set the correct URL scheme for the cache connection based on the CACHE_TLS environment variable. Redis doesn't
  # provide TSL by default and the local Redis container doesn't have any extra configuration for setting up TSL. Since,
  # the admin Docker image is used both in the local and non-local environments, we need to be able to control the TLS
  # setting accordingly. Thus, this setting is mostly needed for using a non-TLS connection in the local environment.
  if [ "$CACHE_TLS" = true ]; then
    CACHE_URL_SCHEME="rediss"
  else
    CACHE_URL_SCHEME="redis"
  fi

  export ONGOING_LOCAL_CACHE_URL="${CACHE_URL_SCHEME}://:${CACHE_PASSWORD}@${CACHE_HOST}/${ONGOING_LOCAL_CACHE_DB}"
fi
export DATABASE_URL="postgis://${DB_APP_USER}:${DB_APP_PASSWORD}@${DB_HOST}/${DB_NAME}"

# Run as exec so the application can receive any Unix signals sent to the container, e.g., Ctrl + C.
exec "$@"
