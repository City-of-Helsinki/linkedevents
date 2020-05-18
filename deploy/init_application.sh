#!/bin/bash
# Linkedevents needs these updated after LANGUAGES has changed
./manage.py sync_translation_fields --noinput
# Templates are a city specific look
./manage.py install_templates helevents
