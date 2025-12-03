# ==============================
FROM helsinki.azurecr.io/ubi9/python-312-gdal AS appbase
# ==============================

# Branch or tag used to pull python-uwsgi-common.
ARG UWSGI_COMMON_REF=main

ENV PYTHONDONTWRITEBYTECODE=true
ENV PYTHONUNBUFFERED=true
# Default for URL prefix, handled by uwsgi, ignored by devserver
# Works like this: "/example" -> http://hostname.domain.name/example
ENV DJANGO_URL_PREFIX=/

WORKDIR /app
USER root

## Setting the permissions beforehand makes the mounted volume inherit the permission
## in docker compose. Useful for development with non-root user and named volume.
## https://github.com/docker/compose/issues/3270#issuecomment-363478501
RUN mkdir -p /var/media && chmod g=u -R /var/media

# Setup Voikko finnish morpho dictionary
RUN mkdir -p /etc/voikko \
    && chmod g=u -R /etc/voikko \
    && cd /etc/voikko \
    && wget https://www.puimula.org/htp/testing/voikko-snapshot-v5/dict-morpho.zip \
    && unzip dict-morpho.zip

COPY requirements.txt .
COPY requirements-prod.txt .

RUN dnf update -y  \
    && dnf install -y nmap-ncat  \
    && pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements-prod.txt \
    && uwsgi --build-plugin https://github.com/City-of-Helsinki/uwsgi-sentry \
    && dnf clean all

# Build and copy specific python-uwsgi-common files.
ADD https://github.com/City-of-Helsinki/python-uwsgi-common/archive/${UWSGI_COMMON_REF}.tar.gz /usr/src/
RUN mkdir -p /usr/src/python-uwsgi-common && \
    tar --strip-components=1 -xzf /usr/src/${UWSGI_COMMON_REF}.tar.gz -C /usr/src/python-uwsgi-common && \
    mkdir /etc/uwsgi && \
    cp /usr/src/python-uwsgi-common/uwsgi-base.ini /etc/uwsgi/ && \
    uwsgi --build-plugin /usr/src/python-uwsgi-common && \
    rm -rf /usr/src/${UWSGI_COMMON_REF}.tar.gz && \
    rm -rf /usr/src/python-uwsgi-common

ENTRYPOINT ["/app/docker/django/docker-entrypoint.sh"]

# ==============================
FROM appbase AS development
# ==============================

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

ENV DEV_SERVER=true

COPY . .

# This is required by osoite importer (by underlying munigeo importers)
RUN mkdir -p data && chgrp -R 0 data && chmod g+w -R data

USER default
EXPOSE 8000/tcp

# ==============================
FROM appbase AS staticbuilder
# ==============================

ENV VAR_ROOT=/app
COPY . .

RUN mkdir -p linkedevents/static \
    && touch linkedevents/static/openapi_schema.yaml \
    && SECRET_KEY="only-used-for-collectstatic" python manage.py spectacular \
    --file linkedevents/static/openapi_schema.yaml --lang en --validate --fail-on-warn \
    --api-version v1 \
    && SECRET_KEY="only-used-for-collectstatic" python manage.py collectstatic --noinput

# ==============================
FROM appbase AS production
# ==============================

COPY --from=staticbuilder /app/static /app/static
COPY  . .

RUN django-admin compilemessages

# This is needed to install preferred templates here.
RUN chgrp -R 0 templates/rest_framework/ && chmod g+w -R templates/rest_framework/

# This is required by osoite importer (by underlying munigeo importers)
RUN mkdir -p data && chgrp -R 0 data && chmod g+w -R data

USER default
EXPOSE 8000/tcp
