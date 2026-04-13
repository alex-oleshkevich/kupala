# ------------------------------------------------------
# STAGE 1 - build frontend assets
# ------------------------------------------------------
FROM node:22-alpine AS frontend
WORKDIR /code

ARG PROJECT=demo
ARG NPM_CONFIG_CACHE=/root/.npm

ADD package.json package-lock.json /code/
RUN --mount=type=cache,target=$NPM_CONFIG_CACHE,sharing=locked \
    npm install
ADD . .
RUN npm run build

# ------------------------------------------------------
# STAGE 2 -- build application image
# ------------------------------------------------------
FROM python:3.13-slim
EXPOSE 8000
WORKDIR /code

ARG PROJECT=demo
ARG RUN_DEPS='gettext nano procps curl'
ARG BUILD_DEPS='git'
ARG PIP_CACHE_DIR=/root/pip-cache
ARG USERNAME=app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_CACHE_DIR=$PIP_CACHE_DIR
ENV VIRTUAL_ENV=.venv
ENV UV_CACHE_DIR=/root/.cache/uv
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PROJECT_ENVIRONMENT=$VIRTUAL_ENV
ENV UV_FROZEN=1
ARG UV_SYNC_ARGS='--no-dev'

RUN useradd -d /code -M -u 1000 $USERNAME

RUN --mount=type=cache,target=/var/lib/apt,sharing=locked \
    --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    set -xe \
    && apt update -y \
    && apt install -y --no-install-recommends $RUN_DEPS

RUN --mount=type=cache,target=/var/lib/apt,sharing=locked \
    --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    --mount=type=cache,target=$PIP_CACHE_DIR,sharing=locked \
    --mount=type=cache,target=$UV_CACHE_DIR,sharing=locked \
    --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    set -xe \
    && apt update -y \
    && apt install -y --no-install-recommends $BUILD_DEPS \
    && update-ca-certificates \
    && uv sync --frozen --no-install-project $UV_SYNC_ARGS \
    && apt remove -y $BUILD_DEPS \
    && apt autoremove -y \
    && apt clean -y

# install project itself. the project changes more often than dependencies
# so it is better to install it after dependencies to keep a good layer cache
RUN --mount=type=cache,target=$UV_CACHE_DIR \
    --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    uv sync --frozen $UV_SYNC_ARGS

USER app
ADD manage.py ./
ADD deploy/docker/* /bin/
ADD --chown=$USERNAME $PROJECT/ $PROJECT/
ADD alembic.ini alembic/ ./

ADD pybabel.ini ./
RUN pybabel compile -D messages -d demo/locale/

COPY --from=frontend /code/$PROJECT/statics/ /code/$PROJECT/statics/

SHELL ["/bin/bash"]
CMD ["/bin/docker-run.sh"]

ARG RELEASE_ID=''
ENV RELEASE_ID=$RELEASE_ID

ARG RELEASE_BRANCH=''
ENV RELEASE_BRANCH=$RELEASE_BRANCH

ARG RELEASE_COMMIT=''
ENV RELEASE_COMMIT=$RELEASE_COMMIT

ARG RELEASE_DATE=''
ENV RELEASE_DATE=$RELEASE_DATE

ARG REPO_URL=''
LABEL org.opencontainers.image.source=$REPO_URL
