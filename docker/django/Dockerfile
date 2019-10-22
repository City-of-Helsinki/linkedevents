FROM python:3.6

# Force flush all messages immediately, not really Docker specific
ENV PYTHONUNBUFFERED 1

RUN apt-get update \
    && apt-get install --no-install-recommends -y gdal-bin python-gdal python3-gdal

COPY requirements.txt /tmp

RUN pip install --upgrade pip \
    && pip install pip-tools \
    && pip install --src /usr/src -r /tmp/requirements.txt

RUN mkdir /app

WORKDIR /app

# Usually overwritten by bind mount from docker-compose.yml
COPY . /app

COPY docker/django/docker-entrypoint.sh /docker-entrypoint.sh

ENTRYPOINT [ "/docker-entrypoint.sh" ]
