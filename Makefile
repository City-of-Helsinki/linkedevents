# This is file used for developing and as a cheatsheet for the developer


.PHONY: build start stop up lint

BASE_DIR = $(shell pwd)
CONTAINER_PORT := $(shell grep CONTAINER_PORT .env | cut -d '=' -f2)

build:
	# @docker-compose build
	# @docker-compose run addit python ./manage.py collectstatic --no-input
	# @docker build -f docker/django/Dockerfile \
	# -t linkedevents .
	@docker build \
	--build-arg BASE_IMAGE_VERSION=3.7-slim \
	-f Dockerfile.dist \
	-t linkedevents \
	.

start:
	@docker start linkedevents

stop:
	@docker stop linkedevents

up:
	@docker run \
	--rm \
	-p 8000:8000 \
	--network=host \
	-e ALLOWED_HOSTS=localhost \
	-e APP_PASSWORD=secret \
	-e APP_USER=linkedevents_application \
	-e DB_HOST=localhost \
	-e DB_NAME=linkedevents \
	-e MIGRATION_PASSWORD=secret \
	-e MIGRATION_USER=linkedevents_migration \
	-e SECRET_KEY=secret \
	-e TOKEN_AUTH_ACCEPTED_AUDIENCE=linkedevents-local \
	-e TOKEN_AUTH_SHARED_SECRET=secret \
	--name linkedevents \
	linkedevents

lint:
	@docker run \
	--rm \
	-v `pwd`:/usr/src/app \
	-w /usr/src/app \
	-u circleci \
	--name linkedevents-lint \
	circleci/python:3.7.6 \
	/bin/bash -c "pip install pip-tools && pip-sync --user requirements-dev.txt"
