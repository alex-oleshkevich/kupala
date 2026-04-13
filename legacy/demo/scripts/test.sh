#!/usr/bin/env bash
set -euo pipefile

# Run unit tests.

export APP_ENV=unittest

pytest $@
