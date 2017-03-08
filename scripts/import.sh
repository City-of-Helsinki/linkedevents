#!/bin/bash

TIMESTAMP_FORMAT="+%Y-%m-%d %H:%M:%S"
ROOT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

LOG_DIRECTORY="$(readlink -m $ROOT_PATH/../logs/import)"
LOG_FILE="$LOG_DIRECTORY/linkedevents-import-$(date "+%Y-%m-%d-%H-%M").log"

HEALTHCHECK_URL="https://hchk.io/65041e32-e8d9-4937-a73a-96ca24a74c51"

if [ -f $ROOT_PATH/local_update_config ]; then
    . $ROOT_PATH/local_update_config
fi

# Ensure the logging directory exists
# -p caused the command not to return error if the directory exists
mkdir -p $LOG_DIRECTORY

# Loggin stanza
# Save stdout & stderr as descriptors 3 & 4
exec 3>&1 4>&2
# Belt and suspenders restoration of descriptors on signaled exit
trap 'exec 2>&4 1>&3' 0 1 2 3
exec 1> $LOG_FILE 2>&1

echo ---------------------------------
echo "$(date "$TIMESTAMP_FORMAT") Starting import"
echo ---------------------------------

cd $ROOT_PATH

echo "$(date "$TIMESTAMP_FORMAT") --- Starting tprek importer ---"

python manage.py event_import tprek --places
if [ $? -ne 0 ]; then
    echo "tprek importer signaled failure"
    LAST_ERROR="tprek"
fi

echo "$(date "$TIMESTAMP_FORMAT") --- Starting matko importer ---"

python manage.py event_import matko --events
if [ $? -ne 0 ]; then
    echo "matko importer signaled failure"
    LAST_ERROR="matko"
fi

echo "$(date "$TIMESTAMP_FORMAT") --- Starting kulke importer ---"

python manage.py event_import kulke --events
if [ $? -ne 0 ]; then
    echo "kulke importer signaled failure"
    LAST_ERROR="kulke"
fi

echo "$(date "$TIMESTAMP_FORMAT") --- Starting helmet importer ---"

python manage.py event_import helmet --events
if [ $? -ne 0 ]; then
    echo "helmet importer signaled failure"
    LAST_ERROR="helmet"
fi

echo "$(date "$TIMESTAMP_FORMAT") --- Starting haystack index update ---"

nice python manage.py update_index -a 1
if [ $? -ne 0 ]; then
    echo "haystack index update signaled failure"
    LAST_ERROR="haystack"
fi

echo "$(date "$TIMESTAMP_FORMAT") --- Starting curl to purge varnish cache ---"

curl -s -X PURGE http://10.1.2.123/linkedevents
if [ $? -ne 0 ]; then
    echo "varnish purge call signaled failure"
    LAST_ERROR="varnish_purge"
fi

echo ---------------------------------
echo "$(date "$TIMESTAMP_FORMAT") Import finished"
echo ---------------------------------

# Notify the Watchers

curl -s $HEALTHCHECK_URL > /dev/null

if [ -n "$LAST_ERROR" ]; then
  echo '{"name": "linkedevents_import", "refresh": 43200, "interval": 3600, "output": "Linkedevents import failed", "status": 1}' | nc localhost 3030 > /dev/null
else
  echo '{"name": "linkedevents_import", "refresh": 43200, "interval": 3600, "ttl": 3800, "output": "Linkedevents import completed successfully", "status": 0}' | nc localhost 3030 > /dev/null
fi

# Output logs to runner if errors happened

if [ -n "$LAST_ERROR" ]; then
    echo "$(date "$TIMESTAMP_FORMAT") At least one step failed. Last step to fail was $LAST_ERROR" >&4
    cat $LOG_FILE >&4
    exit 1
fi
