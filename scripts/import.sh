#!/bin/bash

TIMESTAMP_FORMAT="+%Y-%m-%d %H:%M:%S"
ROOT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

LOG_FILE="/tmp/linkedevents-import-$(date "+%Y-%m-%d-%H-%M").log"

if [ -f $ROOT_PATH/local_update_config ]; then
    $ROOT_PATH/local_update_config
fi
    
echo --------------------------------- >> $LOG_FILE
echo "$(date "$TIMESTAMP_FORMAT") Starting import" >> $LOG_FILE
echo --------------------------------- >> $LOG_FILE
    
cd $ROOT_PATH

echo Importing tprek locations >> $LOG_FILE

python manage.py event_import tprek --locations >> $LOG_FILE 2>&1
if [ $? -ne 0 ]; then
    cat $LOG_FILE
    exit 1
fi

echo Importing Matko events >> $LOG_FILE

python manage.py event_import matko --events >> $LOG_FILE 2>&1
if [ $? -ne 0 ]; then
    cat $LOG_FILE
    exit 1
fi

echo Importing Kulke events >> $LOG_FILE

python manage.py event_import kulke --events >> $LOG_FILE 2>&1
if [ $? -ne 0 ]; then
    cat $LOG_FILE
    exit 1
fi

echo Importing HelMet events >> $LOG_FILE

python manage.py event_import helmet --events >> $LOG_FILE 2>&1
if [ $? -ne 0 ]; then
    cat $LOG_FILE
    exit 1
fi
