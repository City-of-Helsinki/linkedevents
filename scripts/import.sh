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

python manage.py event_import tprek --places >> $LOG_FILE 2>&1
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

nice python manage.py update_index -a 1 >> $LOG_FILE 2>&1
if [ $? -ne 0 ]; then
    cat $LOG_FILE
    exit 1
fi

curl -s -X PURGE http://10.1.2.123/linkedevents >> $LOG_FILE 2>&1
if [ $? -ne 0 ]; then
    cat $LOG_FILE
    exit 1
fi

curl -s https://hchk.io/a6757e9d-2f0e-4668-be3f-a6be74bbc66b > /dev/null

echo --------------------------------- >> $LOG_FILE
echo "$(date "$TIMESTAMP_FORMAT") Import finished" >> $LOG_FILE
echo --------------------------------- >> $LOG_FILE
