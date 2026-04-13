#!/usr/bin/env bash
set -euo pipefile

# Extract messages from the specified directory and update the message catalog template.
# Usage: ./scripts/collect-messages.sh

pybabel extract -o demo/locale/messages.pot demo/
