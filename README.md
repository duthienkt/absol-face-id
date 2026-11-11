# absol-face-id

So sánh ảnh khuôn mặt với ảnh mẫu lưới **3×3** thông qua API PHP.

## Các tệp chính

| Tệp | Chức năng | Nơi chạy |
| --- | --- | --- |
| `server.py` | HTTP server, tải ảnh, cache và so sánh khuôn mặt | Ubuntu |
| `face_id_verification.php` | Nhận URL hoặc file upload, gọi Python và trả kết quả | Web server Ubuntu |
| `scripts/server_start.sh` | Chạy `python3 server.py` trong screen | Ubuntu, dùng `sh` |
| `scripts/server_status.sh` | Kiểm tra phiên screen của server | Ubuntu, dùng `sh` |
| `scripts/server_stop.sh` | Tắt phiên screen và server | Ubuntu, dùng `sh` |
| `scripts/upload_init.sh` | Upload dự án một lần bằng rsync | Mac, dùng Bash |
| `scripts/upload_sync.sh` | Theo dõi thay đổi và gọi upload | Mac, dùng Bash |

## Cách dùng

Cài đặt và cấu hình lần đầu theo [document.md](document.md).

### Ubuntu: quản lý server

Chạy từ thư mục gốc dự án, dùng cùng user `www-data`:

```sh
# Khởi động với Python trong virtualenv.
sudo -u www-data env PATH="$PWD/.venv/bin:$PATH" sh scripts/server_start.sh

# Kiểm tra và dừng.
sudo -u www-data sh scripts/server_status.sh
sudo -u www-data sh scripts/server_stop.sh
```

Kiểm tra HTTP: `curl http://127.0.0.1:5100/ping` → `pong`.
Sau khi cập nhật mã Python, dừng rồi khởi động lại server.

### Mac: upload

Tạo file `.env` ở thư mục gốc dự án, cạnh `README.md`:

```dotenv
UPLOAD_DEST='user@host:/absolute/path/to/absol-face-id/'
```

Thay `user`, `host` và đường dẫn bằng thông tin SSH của máy chủ Ubuntu. Giữ dấu `/` cuối đường dẫn. Hai script upload tự đọc `.env`, kể cả khi chạy từ thư mục khác. File này chỉ cần trên Mac, đã được loại khỏi Git và rsync.

```bash
bash scripts/upload_init.sh   # Upload một lần
bash scripts/upload_sync.sh   # Tự upload khi file thay đổi
```

Nhấn `Ctrl+C` để dừng theo dõi. Hai script upload chỉ chạy trên Mac.

## API PHP

**POST** `/libs/absol-face-id/face_id_verification.php`

| Tham số | Bắt buộc | Giá trị |
| --- | --- | --- |
| `verification_file` | Có | URL HTTP/HTTPS của ảnh mẫu lưới 3×3 |
| `input_file` | Có | URL HTTP/HTTPS hoặc file ảnh upload |

Hỗ trợ `application/json`, `application/x-www-form-urlencoded` khi gửi URL; dùng `multipart/form-data` để upload ảnh, tên trường file là `input_file`. Nếu có cả URL và file cho `input_file`, ưu tiên file. File upload tối đa 20 MiB, còn phụ thuộc giới hạn PHP/web server.

### Gửi URL

```bash
curl 'https://your-domain.example/libs/absol-face-id/face_id_verification.php' \
  -H 'Content-Type: application/json' \
  -d '{"verification_file":"https://images.example/reference-grid.jpg","input_file":"https://images.example/face.jpg"}'
```

### Upload ảnh

```bash
curl 'https://your-domain.example/libs/absol-face-id/face_id_verification.php' \
  -F 'verification_file=https://images.example/reference-grid.jpg' \
  -F 'input_file=@/path/to/face.jpg'
```

### Kết quả JSON

Thành công (HTTP 200):

```json
{"status":"ok","result":0.9}
```

`result` nằm trong khoảng `-1` đến `1`; càng cao càng giống, không phải phần trăm xác suất.

Thất bại:

```json
{"status":"error","message":"Thông báo lỗi chi tiết"}
```

HTTP status thường gặp: `400` tham số/ảnh không hợp lệ, `405` sai phương thức, `500` lỗi xử lý Python, `503` lỗi PHP hoặc kết nối service.

Chi tiết cài đặt, model, cache, quyền truy cập, API Python và xử lý lỗi: [document.md](document.md).
