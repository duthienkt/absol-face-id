#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -f "$PROJECT_DIR/.env" ]; then
  echo 'Thiếu file .env chứa UPLOAD_DEST.' >&2
  exit 1
fi
. "$PROJECT_DIR/.env"
: "${UPLOAD_DEST:?Thiếu UPLOAD_DEST trong .env}"

command -v rsync >/dev/null 2>&1 || {
  echo 'Cần cài rsync để upload.' >&2
  exit 1
}

rsync -az \
  --exclude='.git/' \
  --exclude='node_modules/' \
  --exclude='.env' \
  --exclude='.env.*' \
  --exclude='/scripts/upload_init.sh' \
  --exclude='/scripts/upload_sync.sh' \
  "$PROJECT_DIR/" "$UPLOAD_DEST"
