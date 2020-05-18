# Dockerfile for Linkedevents backend
# Attemps to provide for both local development and server usage

FROM python:3.7-buster

RUN useradd -ms /bin/bash -d /linkedevents linkedevents

WORKDIR /linkedevents

# Can be used to inquire about running app
# eg. by running `echo $APP_NAME`
ENV APP_NAME linkedevents
# This is server out by Django itself, but aided
# by whitenoise by adding cache headers and also delegating
# much of the work to WSGI-server
ENV STATIC_ROOT /srv/static
# For some reason python output buffering buffers much longer
# while in Docker. Maybe the buffer is larger?
ENV PYTHONUNBUFFERED True

# less & netcat-openbsd are there for in-container manual debugging
RUN apt-get update && apt-get install -y gdal-bin postgresql-client less netcat-openbsd
RUN pip install --no-cache-dir uwsgi
# Sentry CLI for sending events from non-Python processes to Sentry
# eg. https://docs.sentry.io/cli/send-event/#bash-hook
RUN curl -sL https://sentry.io/get-cli/ | bash

# Copy requirements files to image for preloading dependencies
# in their own layer
COPY requirements.txt .

# deploy/requirements.txt must reference the base requirements
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Statics are kept inside container image for serving using whitenoise
RUN mkdir -p /srv/static && python manage.py collectstatic

# Keep media in its own directory outside home, in case home
# directory forms some sort of attack route
# Usually this would be some sort of volume
RUN mkdir -p /srv/media && chown linkedevents:linkedevents /srv/media

USER linkedevents

ENTRYPOINT ["deploy/entrypoint.sh"]
