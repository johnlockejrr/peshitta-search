#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export SEARCH_DB="${SEARCH_DB:-$PWD/data/peshitta.db}"
export STATIC_DIR="${STATIC_DIR:-$PWD/dist}"
exec gunicorn backend:app --chdir src -b "0.0.0.0:${PORT:-8000}" --workers "${WORKERS:-2}"
