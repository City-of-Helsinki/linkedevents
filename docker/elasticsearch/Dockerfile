FROM elasticsearch:1.7

RUN apt-get update \
    && apt-get install --no-install-recommends -y libvoikko1 \
    && /usr/share/elasticsearch/bin/plugin -i fi.evident.elasticsearch/elasticsearch-analysis-voikko/0.4.0 \
    && wget http://www.puimula.org/htp/testing/voikko-snapshot-v5/dict-morpho.zip \
    && unzip dict-morpho.zip -d /etc/voikko
