FROM postgres:10

RUN apt-get update && \
    apt-get install -y postgresql-10-postgis-2.5

RUN localedef -i fi_FI -c -f UTF-8 -A /usr/share/locale/locale.alias fi_FI.UTF-8

ENV LANG fi_FI.UTF-8

COPY ./docker-entrypoint.sh /docker-entrypoint-initdb.d/docker-entrypoint.sh
