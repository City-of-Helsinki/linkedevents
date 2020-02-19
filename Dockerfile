FROM python:3.7-buster

RUN useradd -ms /bin/bash -d /linkedevents linkedevents

WORKDIR /linkedevents

# Can be used to inquire about running app
# eg. by running `echo $APP_NAME`
ENV APP_NAME linkedevents
ENV STATIC_ROOT /srv/static

RUN apt-get update && apt-get install -y gdal-bin postgresql-client
RUN pip install --no-cache-dir uwsgi

# Copy requirements files to image for preloading dependencies
# in their own layer
COPY requirements.txt .

# deploy/requirements.txt must reference the base requirements
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Statics are kept inside container image for serving using whitenoise
RUN mkdir -p /srv/static && python manage.py collectstatic

# Keep media in its own directory outside home, in case home
# directory forms some sort of attack route
# Usually this would be some sort of volume
RUN mkdir -p /srv/media && chown linkedevents:linkedevents /srv/media

USER linkedevents

ENTRYPOINT ["deploy/entrypoint.sh"]
