ARG POSTGRES_VERSION=9.6
ARG POSTGIS_VERSION=2.5
ARG IMAGE_VARIANT=alpine

FROM helsinkitest/postgis:${POSTGRES_VERSION}-${POSTGIS_VERSION}-${IMAGE_VARIANT}

# over-writing the parent /docker-entrypoint-initdb.d/10_postgis.sh
COPY ./docker/postgres/docker-entrypoint.sh /docker-entrypoint-initdb.d/10_postgis.sh
COPY ./docker/postgres/init-db.sh /docker-entrypoint-initdb.d/init-db.sh
