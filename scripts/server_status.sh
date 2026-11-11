#!/bin/sh
set -eu

SESSION_NAME='absol-face-id'

command -v screen >/dev/null 2>&1 || {
  echo 'Thiếu screen. Trên Ubuntu/Debian: sudo apt install screen' >&2
  exit 1
}
if screen -S "$SESSION_NAME" -Q windows >/dev/null 2>&1; then
  echo "Server đang chạy trên screen: $SESSION_NAME"
else
  echo "Server không chạy trên screen: $SESSION_NAME"
  exit 1
fi
