#!/usr/bin/env bash
set -euo pipefile

# Run unit tests with coverage.

DIRNAME=$(dirname $BASH_SOURCE[0])
$DIRNAME/test.sh --cov-report term --cov-report html --cov=demo --cov=tests $@
