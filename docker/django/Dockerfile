ARG PYTHON_VERSION=3.9
ARG IMAGE_VARIANT=slim

# ==============================
FROM helsinkitest/python:${PYTHON_VERSION}-${IMAGE_VARIANT} AS appbase
# ==============================
RUN mkdir /entrypoint

ENV PYTHONDONTWRITEBYTECODE=true
ENV PYTHONUNBUFFERED=true
# Default for URL prefix, handled by uwsgi, ignored by devserver
# Works like this: "/example" -> http://hostname.domain.name/example
ENV DJANGO_URL_PREFIX=/

## Setting the permissions beforehand makes the mounted volume inherit the permission
## in docker compose. Useful for development with non-root user and named volume.
## https://github.com/docker/compose/issues/3270#issuecomment-363478501
RUN mkdir -p /var/media && chown -R appuser:appuser /var/media && chmod g=u -R /var/media

COPY --chown=appuser:appuser requirements.txt /app/
COPY --chown=appuser:appuser requirements-prod.txt /app/

RUN apt-install.sh \
    build-essential \
    gdal-bin \
    gettext \
    libpq-dev \
    postgresql-client \
    libcurl4-openssl-dev \
    && pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r /app/requirements.txt \
    && pip install --no-cache-dir -r /app/requirements-prod.txt \
    && uwsgi --build-plugin https://github.com/City-of-Helsinki/uwsgi-sentry \
    && apt-cleanup.sh build-essential

COPY --chown=appuser:appuser ./docker/django/docker-entrypoint.sh /entrypoint/docker-entrypoint.sh
ENTRYPOINT ["/entrypoint/docker-entrypoint.sh"]

# ==============================
FROM appbase AS development
# ==============================

COPY --chown=appuser:appuser requirements-dev.txt /app/
RUN pip install --no-cache-dir -r /app/requirements-dev.txt

ENV DEV_SERVER=true

COPY --chown=appuser:appuser . /app/

# This is required by osoite importer (by underlying munigeo importers)
RUN mkdir -p /app/data && chgrp -R 0 /app/data && chmod g+w -R /app/data

USER appuser

EXPOSE 8000/tcp

# ==============================
FROM appbase AS staticbuilder
# ==============================

ENV VAR_ROOT=/app
COPY --chown=appuser:appuser . /app

RUN mkdir -p /app/linkedevents/static \
    && touch /app/linkedevents/static/openapi_schema.yaml \
    && SECRET_KEY="only-used-for-collectstatic" python manage.py spectacular \
    --file /app/linkedevents/static/openapi_schema.yaml --lang en --validate --fail-on-warn \
    --api-version v1 \
    && SECRET_KEY="only-used-for-collectstatic" python manage.py collectstatic --noinput

# ==============================
FROM appbase AS production
# ==============================

COPY --from=staticbuilder --chown=appuser:appuser /app/static /app/static
COPY --chown=appuser:appuser . /app/

RUN django-admin compilemessages

# This is needed to install preferred templates here.
RUN chgrp -R 0 /app/templates/rest_framework/ && chmod g+w -R /app/templates/rest_framework/

# This is required by osoite importer (by underlying munigeo importers)
RUN mkdir -p /app/data && chgrp -R 0 /app/data && chmod g+w -R /app/data

USER appuser

EXPOSE 8000/tcp
