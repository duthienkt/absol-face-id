#!/bin/sh
set -eu

SESSION_NAME='absol-face-id'

command -v screen >/dev/null 2>&1 || {
  echo 'Thiếu screen. Trên Ubuntu/Debian: sudo apt install screen' >&2
  exit 1
}
if ! screen -S "$SESSION_NAME" -Q windows >/dev/null 2>&1; then
  echo 'Server đã dừng.'
  exit 0
fi

screen -S "$SESSION_NAME" -X quit
echo "Đã tắt server và phiên screen: $SESSION_NAME"
