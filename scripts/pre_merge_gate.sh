#!/usr/bin/env bash
set -euo pipefail

repo_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$repo_root"

run() {
  echo "[merge-gate] $*"
  "$@"
}

require_path() {
  local path="$1"
  if [[ ! -e "$path" ]]; then
    echo "[merge-gate] missing required path: $path" >&2
    exit 1
  fi
}

require_path "AGENTS.md"
require_path "docs/MEMORY.md"
require_path "docs/TODO.md"

run uv sync --python 3.11 --extra dev
run uv run --python 3.11 python -m pytest -q
