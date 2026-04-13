#!/usr/bin/env bash
set -euo pipefile

# Update the message catalogs usign the message catalog template.
# Usage: ./scripts/update-messages.sh

pybabel update -D messages -i demo/locale/messages.pot -d demo/locale/
