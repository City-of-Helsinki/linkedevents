ARG PYTHON_VERSION=3.9
ARG IMAGE_VARIANT=slim

# ==============================
FROM helsinkitest/python:${PYTHON_VERSION}-${IMAGE_VARIANT} AS appbase
# ==============================
RUN mkdir /entrypoint

ENV PYTHONDONTWRITEBYTECODE=true
ENV PYTHONUNBUFFERED=true

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
    postgresql-client \
    && pip install --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt \
    && pip install --no-cache-dir -r /app/requirements-prod.txt \
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

USER appuser

EXPOSE 8000/tcp

# ==============================
FROM appbase AS staticbuilder
# ==============================

ENV VAR_ROOT=/app
COPY --chown=appuser:appuser . /app
RUN SECRET_KEY="only-used-for-collectstatic" python manage.py collectstatic --noinput

# ==============================
FROM appbase AS production
# ==============================

COPY --from=staticbuilder --chown=appuser:appuser /app/static /app/static
COPY --chown=appuser:appuser . /app/

RUN chgrp -R 0 /app/templates/rest_framework/ && chmod g+w -R /app/templates/rest_framework/

USER appuser

EXPOSE 8000/tcp
