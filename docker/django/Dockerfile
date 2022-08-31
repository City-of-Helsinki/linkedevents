ARG PYTHON_VERSION=3.9
ARG IMAGE_VARIANT=slim

# ==============================
FROM helsinkitest/python:${PYTHON_VERSION}-${IMAGE_VARIANT} AS base_stage
# ==============================


ENV PYTHONDONTWRITEBYTECODE true
ENV PYTHONUNBUFFERED true

COPY --chown=appuser:appuser requirements.txt /app/

RUN apt-install.sh build-essential gdal-bin gettext \
    && pip install --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt \
    && pip --no-cache-dir install uwsgi==2.0.18 \
    && apt-cleanup.sh build-essential

# ==============================
FROM base_stage AS development
# ==============================

COPY --chown=appuser:appuser requirements-dev.txt /app/

RUN pip --no-cache-dir install -r /app/requirements-dev.txt

COPY --chown=appuser:appuser . /app/

COPY --chown=appuser:appuser ./docker/django/docker-entrypoint.sh /app/
ENTRYPOINT ["/app/docker/django/docker-entrypoint.sh"]

USER appuser:appuser

EXPOSE 8080
