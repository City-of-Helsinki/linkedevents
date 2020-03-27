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

RUN set -eux \
    && apt-get update && apt-get install -y --no-install-recommends --no-install-suggests \
      gdal-bin \
      gettext \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY --chown=appuser:appuser requirements.txt /app/

RUN pip install --no-cache-dir -r /app/requirements.txt

EXPOSE 8000

ENTRYPOINT ["/tini", "--", "/app/docker/django/docker-entrypoint.sh"]

# ==============================
FROM base_stage AS development
# ==============================

COPY --chown=appuser:appuser requirements-dev.txt /app/
RUN pip --no-cache-dir install -r /app/requirements-dev.txt

USER appuser:appuser

CMD ["runserver"]

# ==============================
FROM base_stage AS production
# ==============================

COPY --chown=appuser:appuser . /app/

USER appuser:appuser
