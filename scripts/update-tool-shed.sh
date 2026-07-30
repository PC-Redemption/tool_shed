#!/bin/sh
set -eu

if command -v python3 >/dev/null 2>&1; then
  exec python3 "$(dirname "$0")/update_snapshot.py" "$@"
fi
if command -v python >/dev/null 2>&1; then
  exec python "$(dirname "$0")/update_snapshot.py" "$@"
fi
echo "Tool Shed requires Python 3." >&2
exit 1
