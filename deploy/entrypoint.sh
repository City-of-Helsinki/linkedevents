#!/bin/bash
TIMESTAMP_FORMAT="+%Y-%m-%d %H:%M:%S"

function _log () {
    echo $(date "$TIMESTAMP_FORMAT"): $RUN_ID: $@
}

function _log_boxed () {
    _log ---------------------------------
    _log $@
    _log ---------------------------------
}

_log_boxed "Linkedevents"

if [ "$1" = "help" ]; then
    _log "This is a container image for running Linkedevents event publication hub"
    _log ""
    _log "By default a production ready server will be started using uWSGI"
    _log "You will need to provide configuration using environment variables, see"
    _log "config_dev.toml for the available variables. Especially important is the"
    _log "database configuration using DATABASE_URL"

    _log "You will need to mount a volume at /srv/media for storing user uploaded"
    _log "media. Otherwise they will be lost at container shutdown."

    _log "In addition to the production server, there are several task commands:"
    _log "runserver: runs Django development server at port 8000"
    _log "migrate: runs Django migrations (manage.py migrate)"

    _log_boxed "This container will now exit, for your convenience"

    exit 0
fi

_log "Start with \`help\` for instructions"

if [ "$1" = "runserver" ]; then
    _log_boxed "Running development server"
    ./manage.py runserver 0:8000
elif [ "$1" = "migrate" ]; then
    _log_boxed "Running migrations"
    ./manage.py migrate
elif [ "$1" = "e" ]; then
    _log_boxed "exec'n $@"
    exec "$@"
else
    _log_boxed "Starting production server"
    exec uwsgi -y deploy/uwsgi.yml
fi

_log_boxed "Linkedevents entrypoint finished"
