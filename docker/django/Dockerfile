ARG PYTHON_VERSION=3.9
ARG IMAGE_VARIANT=slim

# ==============================
FROM helsinkitest/python:${PYTHON_VERSION}-${IMAGE_VARIANT} AS base_stage
# ==============================
RUN chown -R appuser:appuser /app

ENV PYTHONDONTWRITEBYTECODE true
ENV PYTHONUNBUFFERED true

COPY --chown=appuser:appuser requirements.txt /app/

RUN apt-install.sh build-essential gdal-bin gettext \
    && pip install --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt \
    && pip --no-cache-dir install uwsgi==2.0.18 \
    && pip install django-debug-toolbar \
    && apt-cleanup.sh build-essential

COPY --chown=appuser:appuser ./docker/django/docker-entrypoint.sh /app/
ENTRYPOINT ["/app/docker/django/docker-entrypoint.sh"]

# ==============================
FROM base_stage AS development
# ==============================

COPY --chown=appuser:appuser requirements-dev.txt /app/
COPY --chown=appuser:appuser requirements.txt /app/requirements.txt


RUN pip --no-cache-dir install -r /app/requirements-dev.txt

COPY --chown=appuser:appuser . /app/

USER appuser:appuser

EXPOSE 8080

# ==============================
FROM base_stage AS production
# ==============================

COPY --chown=appuser:appuser . /app/

RUN DJANGO_SECRET_KEY="only-used-for-collectstatic" DATABASE_URL="sqlite:///" \
    python manage.py collectstatic --noinput

USER appuser:appuser
