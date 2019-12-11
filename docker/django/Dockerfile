# ==============================
FROM helsinkitest/python:3.6-slim as appbase
# ==============================

# Add Tini init system https://github.com/krallin/tini
ENV TINI_VERSION v0.18.0
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini /tini
RUN chmod +x /tini

RUN apt-install.sh gdal-bin build-essential

COPY --chown=appuser:appuser requirements*.txt /app/

RUN pip install --no-cache-dir \
    -r /app/requirements.txt \
    -r /app/requirements-dev.txt \
    -r /app/requirements-prod.txt

COPY --chown=appuser:appuser . /app/

ENTRYPOINT ["/tini", "--", "/app/docker/django/docker-entrypoint.sh"]
