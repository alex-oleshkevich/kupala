#!/bin/bash

set -e

DEFAULT_APP_PACKAGE="demo"
APPLICATION=${ASGI_APPLICATION:="$DEFAULT_APP_PACKAGE.app:app"}
BIND_PORT=${GUNICORN_PORT:=8000}
LOG_LEVEL=${GUNICORN_LOG_LEVEL:='info'}
FORWARDED_ALLOW_IPS=${GUNICORN_FORWARDED_ALLOW_IPS:='*'}
WORKERS=${GUNICORN_WORKERS:=3}

date

gunicorn \
 --bind 0.0.0.0:$BIND_PORT \
 --name $DEFAULT_APP_PACKAGE \
 --worker-class=uvicorn.workers.UvicornWorker \
 --forwarded-allow-ips=$FORWARDED_ALLOW_IPS \
 --workers=$WORKERS \
 --log-level=$LOG_LEVEL \
 --capture-output \
 --timeout=30 \
 --access-logfile - \
 --access-logformat '%(h)s %(l)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" - %(T)ss' \
 --error-logfile - \
 $APPLICATION
