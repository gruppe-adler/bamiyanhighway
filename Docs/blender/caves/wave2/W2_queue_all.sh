#!/bin/bash
# W2_queue_all.sh <steps> <key> [<key> ...]   runs W2_queue.sh for each key in turn (one Blender job at a time).  Do not edit while running.
STEPS=$1; shift
HERE="$(cd "$(dirname "$0")" && pwd)"
for k in "$@"; do "$HERE/W2_queue.sh" "$k" "$STEPS"; done
echo "ALL DONE"
