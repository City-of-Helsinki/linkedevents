# This is file used for developing and as a cheatsheet for the developer



BASE_DIR = $(shell pwd)
CONTAINER_PORT := $(shell grep CONTAINER_PORT .env | cut -d '=' -f2)

.PHONY: build_dist
build_dist:
	# @docker-compose build
	# @docker-compose run addit python ./manage.py collectstatic --no-input
	# @docker build -f docker/django/Dockerfile \
	# -t linkedevents .
	@docker build \
	--build-arg BASE_IMAGE_VERSION=3.7-slim \
	--target dist \
	-f Dockerfile.dist \
	-t linkedevents \
	.

.PHONY: build_admin
build_admin:
	@docker build \
	--build-arg BASE_IMAGE_VERSION=3.7-slim \
	--target admin \
	-f Dockerfile.dist \
	-t linkedevents-admin \
	.

.PHONY: start
start:
	@docker start linkedevents

.PHONY: stop
stop:
	@docker stop linkedevents

.PHONY: up
up:
	@docker run \
	--rm \
	-p 8000:8000 \
	--network=host \
	-e ALLOWED_HOSTS=localhost \
	-e DB_APP_PASSWORD=secret \
	-e DB_APP_USER=linkedevents_application \
	-e DB_HOST=localhost \
	-e DB_MIGRATION_PASSWORD=secret \
	-e DB_MIGRATION_USER=linkedevents_migration \
	-e DB_NAME=linkedevents \
	-e SECRET_KEY=secret \
	-e TOKEN_AUTH_ACCEPTED_AUDIENCE=linkedevents-local \
	-e TOKEN_AUTH_SHARED_SECRET=secret \
	--name linkedevents \
	linkedevents

.PHONY: lint
lint:
	@docker run \
	--rm \
	-v `pwd`:/usr/src/app \
	-w /usr/src/app \
	-u circleci \
	--name linkedevents-lint \
	circleci/python:3.7.6 \
	/bin/bash -c "pip install pip-tools && pip-sync --user requirements-dev.txt && flake8 ."

.PHONY: import_yso
import_yso:
	@docker run \
	--rm \
	--network=host \
	-e DB_APP_PASSWORD=secret \
	-e DB_APP_USER=linkedevents_application \
	-e DB_HOST=localhost \
	-e DB_NAME=linkedevents \
	--name linkedevents-admin \
	linkedevents-admin \
	python manage.py event_import yso --keywords --all

.PHONY: import_tprek
import_tprek:
	@docker run \
	--rm \
	--network=host \
	-e DB_APP_PASSWORD=secret \
	-e DB_APP_USER=linkedevents_application \
	-e DB_HOST=localhost \
	-e DB_NAME=linkedevents \
	--name linkedevents-admin \
	linkedevents-admin \
	python manage.py event_import tprek --places

.PHONY: import_osoite
import_osoite:
	@docker run \
	--rm \
	--network=host \
	-e DB_APP_PASSWORD=secret \
	-e DB_APP_USER=linkedevents_application \
	-e DB_HOST=localhost \
	-e DB_NAME=linkedevents \
	--name linkedevents-admin \
	linkedevents-admin \
	python manage.py event_import osoite --places

.PHONY: import_helmet
import_helmet:
	@docker run \
	--rm \
	--network=host \
	-e DB_APP_PASSWORD=secret \
	-e DB_APP_USER=linkedevents_application \
	-e DB_HOST=localhost \
	-e DB_NAME=linkedevents \
	--name linkedevents-admin \
	linkedevents-admin \
	python manage.py event_import helmet --events

.PHONY: import_espoo
import_espoo:
	@docker run \
	--rm \
	--network=host \
	-e DB_APP_PASSWORD=secret \
	-e DB_APP_USER=linkedevents_application \
	-e DB_HOST=localhost \
	-e DB_NAME=linkedevents \
	--name linkedevents-admin \
	linkedevents-admin \
	python manage.py event_import espoo --events

.PHONY: install_templates
install_templates:
	@docker run \
	--rm \
	--network=host \
	-e DB_APP_PASSWORD=secret \
	-e DB_APP_USER=linkedevents_application \
	-e DB_HOST=localhost \
	-e DB_NAME=linkedevents \
	--name linkedevents-admin \
	linkedevents-admin \
	python manage.py install_templates helevents

.PHONY: import_finland_municipalities
import_finland_municipalities:
	@docker run \
	--rm \
	--network=host \
	-e DB_APP_PASSWORD=secret \
	-e DB_APP_USER=linkedevents_application \
	-e DB_HOST=localhost \
	-e DB_NAME=linkedevents \
	--name linkedevents-admin \
	linkedevents-admin \
	python manage.py geo_import finland --municipalities

.PHONY: import_helsinki_divisions
import_helsinki_divisions:
	@docker run \
	--rm \
	--network=host \
	-e DB_APP_PASSWORD=secret \
	-e DB_APP_USER=linkedevents_application \
	-e DB_HOST=localhost \
	-e DB_NAME=linkedevents \
	--name linkedevents-admin \
	linkedevents-admin \
	python manage.py geo_import helsinki --divisions

.PHONY: add_helsinki_audience
add_helsinki_audience:
	@docker run \
	--rm \
	--network=host \
	-e DB_APP_PASSWORD=secret \
	-e DB_APP_USER=linkedevents_application \
	-e DB_HOST=localhost \
	-e DB_NAME=linkedevents \
	--name linkedevents-admin \
	linkedevents-admin \
	python manage.py add_helsinki_audience

.PHONY: add_helsinki_topics
add_helsinki_topics:
	@docker run \
	--rm \
	--network=host \
	-e DB_APP_PASSWORD=secret \
	-e DB_APP_USER=linkedevents_application \
	-e DB_HOST=localhost \
	-e DB_NAME=linkedevents \
	--name linkedevents-admin \
	linkedevents-admin \
	python manage.py add_helsinki_topics

.PHONY: createsuperuser
createsuperuser:
	@docker run \
	--rm \
	-it \
	--network=host \
	-e DB_APP_PASSWORD=secret \
	-e DB_APP_USER=linkedevents_application \
	-e DB_HOST=localhost \
	-e DB_NAME=linkedevents \
	--name linkedevents-admin \
	linkedevents-admin \
	python manage.py createsuperuser
