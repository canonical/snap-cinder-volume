#!/usr/bin/env bash
# Regenerate tools/cinder-volume.plugs.data from the store snap
# declaration of the cinder-volume snap.
set -euo pipefail

cd "$(dirname "$0")/.."

tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT

snap known snap-declaration snap-name=cinder-volume | \
  sed '/^$/Q' | \
  python3 -c 'import sys, yaml, json; print(json.dumps(yaml.safe_load(sys.stdin)["plugs"], indent=2))' \
  >"$tmp"

mv "$tmp" tools/cinder-volume.plugs.data
trap - EXIT
