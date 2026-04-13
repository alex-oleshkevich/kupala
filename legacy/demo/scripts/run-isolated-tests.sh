#!/usr/bin/env bash

# This script is used to run tests in an isolated and reproducible Docker environment.
# It builds the Docker images, runs the tests, and then removes the containers.
# This is useful for running tests in a CI/CD pipeline or locally without installing dependencies.

set -euo pipefile

export APP_ENV=unittest
export COMPOSE_PROJECT_NAME="{{ project_slug }}-unitests"


function cleanup {
    docker compose -f compose.yml down -v --remove-orphans
}

trap cleanup EXIT ERR

mkdir -p build
docker compose build --pull
docker compose -f compose.yml run --rm app alembic upgrade head
docker compose -f compose.yml run --user 0 --rm app ./scripts/testcover.sh $@
