#!/bin/sh
set -eu

PROJECT_DIR="$(cd -- "$(dirname -- "$0")/.." && pwd)"
SESSION_NAME='absol-face-id'

command -v screen >/dev/null 2>&1 || {
  echo 'Thiếu screen. Trên Ubuntu/Debian: sudo apt install screen' >&2
  exit 1
}
command -v python3 >/dev/null 2>&1 || {
  echo 'Thiếu python3.' >&2
  exit 1
}
if screen -S "$SESSION_NAME" -Q windows >/dev/null 2>&1; then
  echo "Server đã có phiên screen: $SESSION_NAME"
  exit 0
fi
if [ ! -f "$PROJECT_DIR/server.py" ]; then
  echo 'Không tìm thấy server.py trong thư mục gốc dự án.' >&2
  exit 1
fi

cd -- "$PROJECT_DIR"
# Run Python directly so the screen session closes when Python exits.
screen -dmS "$SESSION_NAME" python3 server.py
sleep 1
if screen -S "$SESSION_NAME" -Q windows >/dev/null 2>&1; then
  echo "Server đang chạy trên screen: $SESSION_NAME"
  echo "Xem server: screen -r $SESSION_NAME"
else
  echo 'Server đã thoát ngay sau khi khởi động. Kiểm tra nội dung server.py.' >&2
  exit 1
fi
