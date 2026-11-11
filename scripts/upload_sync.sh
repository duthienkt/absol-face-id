#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

command -v fswatch >/dev/null 2>&1 || {
  echo 'Cần cài fswatch: brew install fswatch' >&2
  exit 1
}

echo 'Đang theo dõi thay đổi để upload. Nhấn Ctrl+C để dừng.'
fswatch -o \
  --exclude='/\.git(/|$)' \
  --exclude='/node_modules(/|$)' \
  --exclude='/\.env($|\.)' \
  "$PROJECT_DIR" |
while IFS= read -r event; do
  bash "$PROJECT_DIR/scripts/upload_init.sh"
done
