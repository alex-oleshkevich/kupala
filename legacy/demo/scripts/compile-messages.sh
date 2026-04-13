#!/usr/bin/env bash
set -euo pipefile

# Compile message catalogs into binary format.
# Usage: ./scripts/compile-messages.sh

pybabel compile -D messages -d demo/locale/
