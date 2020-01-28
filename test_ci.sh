#!/bin/bash
# Set up db container and run tests in another Python container
# You could also declare multiple Docker images in the executor in CircleCI. That way you could access the db container
# directly from the primary container. However, that would require that the db image would be in a Docker repository.
# See https://circleci.com/docs/2.0/executor-types/#using-multiple-docker-images
# See https://circleci.com/docs/2.0/building-docker-images/#separation-of-environments

set -uxo pipefail

# Create a dummy container which will hold a volume with the source code
docker create \
  -v /usr/src/app \
  -v /home/circleci/.local/bin \
  -v /home/circleci/"${SITE_PACKAGES_PATH}" \
  --name code \
  circleci/python:"${PYTHON_IMAGE_VERSION}" \
  /bin/true

# Copy source code into this volume
docker cp \
  . \
  code:/usr/src/app
# Copy Python dependencies into this volume
docker cp \
  /home/circleci/.local/bin/. \
  code:/home/circleci/.local/bin
docker cp \
  /home/circleci/"${SITE_PACKAGES_PATH}"/. \
  code:/home/circleci/"${SITE_PACKAGES_PATH}"

# Build db container
docker build \
  -t espooevents-service-db \
  -f ./docker/postgres/Dockerfile \
  .

# Run db container (use existing exported env vars)
docker run \
  -d \
  --rm \
  -p 5432:5432 \
  -e POSTGRES_USER \
  -e POSTGRES_PASSWORD \
  -e POSTGRES_DB \
  --name espooevents-service-db \
  espooevents-service-db

# Run tests in another container in the same network as `espooevents-service-db`, this way we have
# all exposed ports from `espooevents-service-db` available on `localhost` in this new container
docker run \
  --rm \
  --network container:espooevents-service-db \
  --volumes-from code \
  -w /usr/src/app \
  --name espooevents-service \
  circleci/python:"${PYTHON_IMAGE_VERSION}" \
  /bin/bash -c " \
    sudo apt-get update && \
    sudo apt-get install -y libgdal-dev && \
    sudo chown -R circleci:circleci /usr/src/app && \
    py.test events"
# Store the exit code of the last command
espooevents_service_check=$?
docker stop espooevents-service-db
docker rm code
# Return the exit code of the jest command
(exit $espooevents_service_check)
