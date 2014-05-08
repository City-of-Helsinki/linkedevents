#!/bin/bash

TIMESTAMP_FORMAT="+%Y-%m-%d %H:%M:%S"
ROOT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

LOG_FILE="/tmp/linkedevents-export-$(date "+%Y-%m-%d-%H-%M").log"

if [ -f $ROOT_PATH/local_update_config ]; then
    $ROOT_PATH/local_update_config
fi

echo --------------------------------- >> $LOG_FILE
echo "$(date "$TIMESTAMP_FORMAT") Starting export" >> $LOG_FILE
echo --------------------------------- >> $LOG_FILE

cd $ROOT_PATH

echo Exporting to CitySDK >> $LOG_FILE

python manage.py event_export CitySDK --new >> $LOG_FILE 2>&1
if [ $? -ne 0 ]; then
    cat $LOG_FILE
    exit 1
fi
