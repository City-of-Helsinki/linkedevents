# This is file used for developing and as a cheatsheet for the developer


.PHONY: build start stop up lint

BASE_DIR = $(shell pwd)
CONTAINER_PORT := $(shell grep CONTAINER_PORT .env | cut -d '=' -f2)

build:
	# @docker-compose build
	# @docker-compose run addit python ./manage.py collectstatic --no-input
	# @docker build -f docker/django/Dockerfile \
	# -t linkedevents .
	@docker build -f Dockerfile.dist -t linkedevents .

start:
	@docker start linkedevents

stop:
	@docker stop linkedevents

up:
	@docker run \
	--env PRODUCTION=true \
	--env DEBUG=false \
	--env DATABASE_URL=postgres://linkedevents_application:secret@localhost:5555/linkedevents \
	-p 127.0.0.1:8000:8000 \
	--name linkedevents \
	-it \
	--rm \
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
