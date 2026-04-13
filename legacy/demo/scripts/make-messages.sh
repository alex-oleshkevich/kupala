#!/usr/bin/env bash
set -euo pipefile

# A shortcut to collect, update and compile messages in one go.

DIRNAME=$(dirname $BASH_SOURCE[0])

bash ./$DIRNAME/collect-messages.sh
bash ./$DIRNAME/update-messages.sh
bash ./$DIRNAME/compile-messages.sh
