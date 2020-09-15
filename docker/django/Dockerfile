ARG PYTHON_VERSION=3.6
ARG IMAGE_VARIANT=slim

# ==============================
FROM helsinkitest/python:${PYTHON_VERSION}-${IMAGE_VARIANT} AS base_stage
# ==============================

ENV PYTHONDONTWRITEBYTECODE true
ENV PYTHONUNBUFFERED true

# Add tini init system https://github.com/krallin/tini
ENV TINI_VERSION v0.18.0
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini /tini
RUN chmod +x /tini

EXPOSE 8000

COPY --chown=appuser:appuser ./docker/django/docker-entrypoint.sh /app/
ENTRYPOINT ["/tini", "--", "/app/docker/django/docker-entrypoint.sh"]

COPY --chown=appuser:appuser requirements.txt /app/

RUN apt-install.sh build-essential gdal-bin gettext \
    && pip install --no-cache-dir -r /app/requirements.txt \
    && pip --no-cache-dir install uwsgi==2.0.18 \
    && apt-cleanup.sh build-essential

# ==============================
FROM base_stage AS development
# ==============================

COPY --chown=appuser:appuser requirements-dev.txt /app/
RUN pip --no-cache-dir install -r /app/requirements-dev.txt

COPY --chown=appuser:appuser . /app/

USER appuser:appuser

# ==============================
FROM base_stage AS production
# ==============================

COPY --chown=appuser:appuser . /app/

RUN DJANGO_SECRET_KEY="only-used-for-collectstatic" DATABASE_URL="sqlite:///" \
    python manage.py collectstatic --noinput

USER appuser:appuser
