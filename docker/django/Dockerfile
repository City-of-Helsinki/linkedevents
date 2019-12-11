# ==============================
FROM helsinkitest/python:3.6-slim as appbase
# ==============================

RUN apt-install.sh gdal-bin build-essential

COPY --chown=appuser:appuser requirements*.txt /app/

RUN pip install --no-cache-dir \
    -r /app/requirements.txt \
    -r /app/requirements-dev.txt \
    -r /app/requirements-prod.txt

COPY --chown=appuser:appuser . /app/

ENTRYPOINT ["/app/docker/django/docker-entrypoint.sh"]
