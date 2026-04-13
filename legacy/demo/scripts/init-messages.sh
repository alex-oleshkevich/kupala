#!/usr/bin/env bash
set -euo pipefile

# Generate a new message catalog for the specified locale from the template.
# Usage: ./scripts/init-messages.sh pl

if [ -z "$1" ]; then
    echo "Please specify the locale code."
    exit 1
fi

pybabel init -D messages -l $1 -d demo/locale/ -i demo/locale/messages.pot
