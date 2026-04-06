#!/usr/bin/env bash
set -euo pipefail

# Compile dependency locks from *.in files using pip-compile.
# Usage: ./scripts/compile-requirements.sh [--upgrade]
# Requires pip-tools (pip install pip-tools).

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

UPGRADE_FLAG=""
if [[ ${1:-} == "--upgrade" ]]; then
  UPGRADE_FLAG="--upgrade"
fi

if ! command -v pip-compile >/dev/null 2>&1; then
  echo "pip-compile not found. Install with: pip install pip-tools" >&2
  exit 1
fi

pip-compile ${UPGRADE_FLAG} --generate-hashes requirements.in -o requirements.txt
pip-compile ${UPGRADE_FLAG} --generate-hashes tests/requirements-dev.in -o tests/requirements-dev.txt

echo "✓ requirements.txt and tests/requirements-dev.txt updated"
