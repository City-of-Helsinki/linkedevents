FROM python:3.6

# Add Tini init system https://github.com/krallin/tini
ENV TINI_VERSION v0.18.0
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini /tini
RUN chmod +x /tini
ENTRYPOINT ["/tini", "--"]

ENV PYTHONUNBUFFERED 0

RUN apt-get update \
    && apt-get install --no-install-recommends -y gdal-bin python-gdal python3-gdal

COPY requirements.txt /usr/src/

RUN pip install --upgrade pip \
    && pip install pip-tools \
    && pip install --src /usr/src -r /usr/src/requirements.txt

RUN mkdir /code

WORKDIR /code

COPY . /code
