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


if [ "$1" = "" ]; then
    _log_boxed "Linkedevents backend development container started"

    _log "This container does not run any processes by default. However, there"
    _log "are some convenience commands available through the entrypoint:"
    _log "runserver: runs manage.py runserver 0:8000"
    _log "migrate: runs manage.py migrate"

    _log_boxed "This container will now exit, for your convenience"

    exit 0
fi

if [ "$1" = "runserver" ]; then
    _log_boxed "Running linkedevents dev server"
    ./manage.py runserver 0:8000
elif [ "$1" = "migrate" ]; then
    _log_boxed "Running linkedevents migrations"
    ./manage.py migrate
else
    _log_boxed "exec'n $@"
    exec "$@"
fi

_log_boxed "Entrypoint finished"
