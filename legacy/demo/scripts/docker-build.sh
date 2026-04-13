#!/usr/bin/env bash

set -e

GIT_REPO=$(git config --get remote.origin.url || true)
GIT_COMMIT=$(git rev-parse HEAD || true)
GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD || true)
RELEASE_ID=$(git describe --tags --exact-match 2>/dev/null || echo "latest")

BASE_IMAGE_NAME="demo"
IMAGE_NAME="$BASE_IMAGE_NAME:$GIT_COMMIT"
CACHE_IMAGE_NAME="$BASE_IMAGE_NAME:$GIT_BRANCH-cache"

docker pull $CACHE_IMAGE_NAME || true

docker build \
    --cache-from $CACHE_IMAGE_NAME \
    --build-arg PROJECT=app \
    --build-arg REPO_URL=$GIT_REPO \
    --build-arg RELEASE_ID=$RELEASE_ID \
    --build-arg RELEASE_BRANCH=$GIT_BRANCH \
    --build-arg RELEASE_COMMIT=$GIT_COMMIT \
    --build-arg RELEASE_DATE="$(date)" \
    -t $IMAGE_NAME .
