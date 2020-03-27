#!/bin/bash
# Set up db container and run tests in another Python container
# You could also declare multiple Docker images in the executor in CircleCI. That way you could access the db container
# directly from the primary container. However, that would require that the db image would be in a Docker repository.
# See https://circleci.com/docs/2.0/executor-types/#using-multiple-docker-images
# See https://circleci.com/docs/2.0/building-docker-images/#separation-of-environments

set -uxo pipefail

# Build db container
docker build \
  -t linkedevents-db \
  -f ./docker/postgres/Dockerfile \
  .

# Build test container
docker build \
  --target development \
  -t linkedevents-test \
  -f ./docker/django/Dockerfile \
  .

# Create a dummy container which will hold a volume with the source code
docker create \
  -v /app \
  --name code \
  linkedevents-test \
  /bin/true

# Copy source code into this volume
docker cp \
  . \
  code:/app

# Run db container (use existing exported env vars)
docker run \
  -d \
  --rm \
  -p 5432:5432 \
  -e POSTGRES_USER \
  -e POSTGRES_PASSWORD \
  -e POSTGRES_DB \
  -e DB_MIGRATION_USER \
  -e DB_MIGRATION_PASSWORD \
  -e DB_APP_USER \
  -e DB_APP_PASSWORD \
  --name linkedevents-db \
  linkedevents-db

# Run tests in another container in the same network as `linkedevents-db`, this way we have
# all exposed ports from `linkedevents-db` available on `localhost` in this new container
docker run \
  --rm \
  --network container:linkedevents-db \
  --volumes-from code \
  -w /app \
  -e WAIT_FOR_IT_ADDRESS=localhost:5432 \
  --name linkedevents \
  linkedevents-test \
  py.test events helevents
# Store the exit code of the last command
linkedevents_check=$?
docker stop linkedevents-db
docker rm code
# Return the exit code of the jest command
(exit $linkedevents_check)
