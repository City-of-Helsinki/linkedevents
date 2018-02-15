#!/bin/bash

TIMESTAMP_FORMAT="+%Y-%m-%d %H:%M:%S"
ROOT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

LOG_DIRECTORY="$(readlink -m $ROOT_PATH/../logs/import)"
LOG_FILE="$LOG_DIRECTORY/linkedevents-import-$(date "+%Y-%m-%d-%H-%M").log"

HEALTHCHECK_URL="https://hchk.io/65041e32-e8d9-4937-a73a-96ca24a74c51"

if [ -f $ROOT_PATH/local_update_config ]; then
    . $ROOT_PATH/local_update_config
fi

function _log () {
    echo $(date "$TIMESTAMP_FORMAT"): $RUN_ID: $@
}

# Identifier to separate runs in logs, if messages end up
# in same file accidentally
RUN_ID=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 4)

# Ensure the logging directory exists
# -p caused the command not to return error if the directory exists
mkdir -p $LOG_DIRECTORY

# Loggin stanza
# Save stdout & stderr as descriptors 3 & 4
exec 3>&1 4>&2
# Belt and suspenders restoration of descriptors on signaled exit
trap 'exec 2>&4 1>&3' 0 1 2 3
exec 1> $LOG_FILE 2>&1

_log ---------------------------------
_log "Starting import"
_log ---------------------------------

cd $ROOT_PATH

_log "--- Starting tprek importer ---"

timeout --preserve-status -s INT 2m python manage.py event_import tprek --places
if [ $? -ne 0 ]; then
    _log "tprek importer signaled failure"
    LAST_ERROR="tprek"
fi

_log "--- Starting matko importer ---"

timeout --preserve-status -s INT 10m python manage.py event_import matko --events
if [ $? -ne 0 ]; then
    _log "matko importer signaled failure"
    LAST_ERROR="matko"
fi

_log "--- Starting kulke importer ---"

timeout --preserve-status -s INT 5m python manage.py event_import kulke --events
if [ $? -ne 0 ]; then
    _log "kulke importer signaled failure"
    LAST_ERROR="kulke"
fi

_log "--- Starting helmet importer ---"

timeout --preserve-status -s INT 5m python manage.py event_import helmet --events
if [ $? -ne 0 ]; then
    _log "helmet importer signaled failure"
    LAST_ERROR="helmet"
fi

_log "--- Starting keyword and place n_events update ---"

nice python manage.py update_n_events
if [ $? -ne 0 ]; then
    _log "keyword and place n_events update signaled failure"
    LAST_ERROR="n_events"
fi

_log "--- Starting haystack index update ---"

nice python manage.py update_index -a 1
if [ $? -ne 0 ]; then
    _log "haystack index update signaled failure"
    LAST_ERROR="haystack"
fi

_log "--- Starting curl to purge varnish cache ---"

curl -s -X PURGE http://10.1.2.123/linkedevents
if [ $? -ne 0 ]; then
    _log "varnish purge call signaled failure"
    LAST_ERROR="varnish_purge"
fi

_log "---------------------------------"
_log "Import finished"
_log "---------------------------------"

# Notify the Watchers

curl -s $HEALTHCHECK_URL > /dev/null

if [ -n "$LAST_ERROR" ]; then
  echo '{"name": "linkedevents_import", "refresh": 43200, "interval": 3600, "output": "Linkedevents import failed", "status": 1}' | nc localhost 3030 > /dev/null
else
  echo '{"name": "linkedevents_import", "refresh": 43200, "interval": 3600, "ttl": 3800, "output": "Linkedevents import completed successfully", "status": 0}' | nc localhost 3030 > /dev/null
fi

# Output logs to runner if errors happened

if [ -n "$LAST_ERROR" ]; then
    _log "At least one step failed. Last step to fail was $LAST_ERROR" >&4
    cat $LOG_FILE >&4
    exit 1
fi
