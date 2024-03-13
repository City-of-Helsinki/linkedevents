# This is file used for developing and as a cheatsheet for the developer

.PHONY: build
build:
	@docker build \
	--target development \
	-f docker/django/Dockerfile \
	-t linkedevents-build \
	.

.PHONY: build_dist
build_dist:
	@docker build \
	--build-arg BASE_IMAGE_VERSION=3.7-slim \
	--target dist \
	-f Dockerfile.dist \
	-t linkedevents \
	.

.PHONY: build_admin
build_admin:
	@docker build \
	--build-arg BASE_IMAGE_VERSION=3.7.12-slim-buster \
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
	--network=host \
	-e WAIT_FOR_IT_ADDRESS=localhost:5432 \
	-v `pwd`:/app \
	-w /app \
	--name linkedevents-lint \
	linkedevents-build \
	flake8 .

.PHONY: test
test:
	@docker run \
	--rm \
	--network=host \
	-e WAIT_FOR_IT_ADDRESS=localhost:5432 \
	-v `pwd`:/app \
	-w /app \
	--name linkedevents-test \
	linkedevents-build \
	py.test events helevents

.PHONY: test2
test2:
	@docker run \
	--rm \
	--network=host \
	-e DB_APP_PASSWORD=secret \
	-e DB_APP_USER=linkedevents_application \
	-e DB_HOST=localhost \
	-e DB_NAME=linkedevents \
	-e SYSTEM_DATA_SOURCE_ID=espooevents \
	--name linkedevents-test \
	linkedevents \
	py.test events helevents

.PHONY: import_yso
import_yso:
	@docker run \
	--rm \
	--network=host \
	-e DB_APP_PASSWORD=secret \
	-e DB_APP_USER=linkedevents_application \
	-e DB_HOST=localhost \
	-e DB_NAME=linkedevents \
	-e SYSTEM_DATA_SOURCE_ID=espooevents \
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
	-e SYSTEM_DATA_SOURCE_ID=espooevents \
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
	-e SYSTEM_DATA_SOURCE_ID=espooevents \
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
	-e HELMET_CITY=espoo \
	-e SYSTEM_DATA_SOURCE_ID=espooevents \
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
	-e SYSTEM_DATA_SOURCE_ID=espooevents \
	--name linkedevents-admin \
	linkedevents-admin \
	python manage.py event_import espoo --events

.PHONY: import_finland_municipalities
import_finland_municipalities:
	@docker run \
	--rm \
	--network=host \
	-e DB_APP_PASSWORD=secret \
	-e DB_APP_USER=linkedevents_application \
	-e DB_HOST=localhost \
	-e DB_NAME=linkedevents \
	-e SYSTEM_DATA_SOURCE_ID=espooevents \
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
	-e SYSTEM_DATA_SOURCE_ID=espooevents \
	--name linkedevents-admin \
	linkedevents-admin \
	python manage.py geo_import helsinki --divisions

.PHONY: add_espoo_audience
add_espoo_audience:
	@docker run \
	--rm \
	--network=host \
	-e DB_APP_PASSWORD=secret \
	-e DB_APP_USER=linkedevents_application \
	-e DB_HOST=localhost \
	-e DB_NAME=linkedevents \
	-e SYSTEM_DATA_SOURCE_ID=espooevents \
	--name linkedevents-admin \
	linkedevents-admin \
	python manage.py add_espoo_audience

.PHONY: add_espoo_topics
add_espoo_topics:
	@docker run \
	--rm \
	--network=host \
	-e DB_APP_PASSWORD=secret \
	-e DB_APP_USER=linkedevents_application \
	-e DB_HOST=localhost \
	-e DB_NAME=linkedevents \
	-e SYSTEM_DATA_SOURCE_ID=espooevents \
	--name linkedevents-admin \
	linkedevents-admin \
	python manage.py add_espoo_topics

.PHONY: add_espoo_places
add_espoo_places:
	@docker run \
	--rm \
	--network=host \
	-e DB_APP_PASSWORD=secret \
	-e DB_APP_USER=linkedevents_application \
	-e DB_HOST=localhost \
	-e DB_NAME=linkedevents \
	-e SYSTEM_DATA_SOURCE_ID=espooevents \
	--name linkedevents-admin \
	linkedevents-admin \
	python manage.py add_espoo_places

.PHONY: update_keywords
update_keywords:
	@docker run \
	--rm \
	--network=host \
	-e DB_APP_PASSWORD=secret \
	-e DB_APP_USER=linkedevents_application \
	-e DB_HOST=localhost \
	-e DB_NAME=linkedevents \
	-e SYSTEM_DATA_SOURCE_ID=espooevents \
	--name linkedevents-admin \
	linkedevents-admin \
	python manage.py update_n_events keyword

.PHONY: update_places
update_places:
	@docker run \
	--rm \
	--network=host \
	-e DB_APP_PASSWORD=secret \
	-e DB_APP_USER=linkedevents_application \
	-e DB_HOST=localhost \
	-e DB_NAME=linkedevents \
	-e SYSTEM_DATA_SOURCE_ID=espooevents \
	--name linkedevents-admin \
	linkedevents-admin \
	python manage.py update_n_events place

.PHONY: update_upcoming_events
update_upcoming_events:
	@docker run \
	--rm \
	--network=host \
	-e DB_APP_PASSWORD=secret \
	-e DB_APP_USER=linkedevents_application \
	-e DB_HOST=localhost \
	-e DB_NAME=linkedevents \
	-e SYSTEM_DATA_SOURCE_ID=espooevents \
	--name linkedevents-admin \
	linkedevents-admin \
	python manage.py update_has_upcoming_events

.PHONY: populate_local_event_cache
populate_local_event_cache:
	@docker run \
	--rm \
	--network=host \
	-e ONGOING_LOCAL_CACHE_DB=2 \
	-e CACHE_HOST=localhost \
	-e CACHE_PASSWORD=secret \
	-e CACHE_TLS=false \
	-e DB_APP_PASSWORD=secret \
	-e DB_APP_USER=linkedevents_application \
	-e DB_HOST=localhost \
	-e DB_NAME=linkedevents \
	-e SYSTEM_DATA_SOURCE_ID=espooevents \
	--name linkedevents-admin \
	linkedevents-admin \
	python manage.py populate_local_event_cache

.PHONY: install_templates
install_templates:
	@docker run \
	--rm \
	--network=host \
	-e DB_APP_PASSWORD=secret \
	-e DB_APP_USER=linkedevents_application \
	-e DB_HOST=localhost \
	-e DB_NAME=linkedevents \
	-v `pwd`:/app \
	-w /app \
	--name linkedevents-admin \
	linkedevents-admin \
	python manage.py install_templates helevents

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

.PHONY: make_migrations
make_migrations:
	@docker run \
		-i \
        --rm \
        --network=host \
        -e DB_APP_PASSWORD=secret \
        -e DB_APP_USER=linkedevents_migration \
        -e DB_HOST=localhost \
        -e DB_NAME=linkedevents \
        -v `pwd`:/app \
        -w /app \
        --name linkedevents-admin \
        linkedevents-admin \
        python manage.py makemigrations

.PHONY: migrate
migrate:
	@docker run \
		-i \
        --rm \
        --network=host \
        -e DB_APP_PASSWORD=secret \
        -e DB_APP_USER=linkedevents_migration \
        -e DB_HOST=localhost \
        -e DB_NAME=linkedevents \
        -v `pwd`:/app \
        -w /app \
        --name linkedevents-admin \
        linkedevents-admin \
        python manage.py migrate
