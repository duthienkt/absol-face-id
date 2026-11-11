# Tài liệu kỹ thuật absol-face-id

Hướng dẫn sử dụng nhanh và API PHP: [README.md](README.md).

## Kiến trúc và nhận diện

Dịch vụ so sánh khuôn mặt bằng Python/OpenCV, với endpoint PHP để nhận request từ client. Python chỉ lắng nghe tại `127.0.0.1:5100`; PHP gọi nội bộ bằng cURL.

Ảnh mẫu gồm các góc mặt của cùng một người, xếp thành lưới **3×3**. Server chia ảnh thành 9 ô, so sánh từng khuôn mặt với ảnh đầu vào và trả về **điểm cosine cao nhất** trong khoảng `-1` đến `1`. Điểm càng cao càng giống; đây không phải phần trăm xác suất. Nếu một ảnh hoặc một ô có nhiều khuôn mặt, chọn mặt có diện tích lớn nhất. Ô không phát hiện được mặt sẽ bị bỏ qua.

## Cài đặt trên Ubuntu

Chạy trong thư mục gốc dự án. Cần Python 3.8 trở lên, PHP 7.3 trở lên với extension cURL, và web server đã cấu hình chạy PHP.

```sh
sudo apt update
sudo apt install python3 python3-venv screen php-curl
python3 -m venv .venv
.venv/bin/python3 -m pip install --upgrade pip
.venv/bin/python3 -m pip install 'opencv-python-headless>=4.10'
.venv/bin/python3 -c 'import cv2; print(cv2.__version__)'
```

Nếu web server dùng PHP theo phiên bản riêng, cài extension cURL tương ứng và reload dịch vụ PHP/web server để extension có hiệu lực.

Python và PHP nên chạy cùng user `www-data` để đọc được file upload tạm có quyền riêng tư. Tạo các thư mục dữ liệu và cấp quyền:

```sh
sudo mkdir -p cache temp models
sudo chown -R www-data:www-data cache temp models
```

User `www-data` cần quyền đọc mã nguồn, model và virtualenv, cùng quyền đi qua các thư mục cha. Không cần đổi chủ sở hữu toàn bộ mã nguồn.

Hai model sau được tải tự động vào `models/` ở lần xác minh đầu tiên:

- `face_detection_yunet_2023mar.onnx`
- `face_recognition_sface_2021dec.onnx`

Lần đầu cần kết nối tới kho OpenCV Zoo trên GitHub và có thể chậm hơn. Các request sau dùng lại model trong bộ nhớ. Khởi động lại server sẽ nạp lại model từ đĩa khi có request xác minh đầu tiên.

## Quản lý server trên Ubuntu

Tên phiên screen là `absol-face-id`. Cả ba lệnh phải chạy bằng **cùng user**. Từ thư mục gốc dự án:

```sh
# Đưa Python của virtualenv vào PATH khi khởi động screen.
sudo -u www-data env PATH="$PWD/.venv/bin:$PATH" sh scripts/server_start.sh

sudo -u www-data sh scripts/server_status.sh
sudo -u www-data sh scripts/server_stop.sh
```

`server_start.sh` tự chuyển về thư mục gốc, không tạo thêm phiên nếu đã có, và kiểm tra lại sau 1 giây. `server_status.sh` trả exit code `0` nếu có phiên, `1` nếu không có. Đây là kiểm tra phiên screen; kiểm tra HTTP bằng `/ping` để biết server có trả lời hay không.

Sau khi cập nhật `server.py`, chạy stop rồi start để áp dụng. Screen giữ tiến trình chạy khi ngắt SSH, nhưng không tự khởi động sau khi reboot hoặc tự chạy lại khi Python lỗi.

Xem console của server:

```sh
sudo -u www-data screen -r absol-face-id
```

Nhấn `Ctrl+A`, rồi `D` để rời screen và giữ server chạy. `Ctrl+C` sẽ dừng Python.

Kiểm tra HTTP từ chính máy chủ:

```sh
curl http://127.0.0.1:5100/ping
# pong
```

## API Python nội bộ

### POST /face_id_verification

Hỗ trợ JSON, `application/x-www-form-urlencoded` và các trường văn bản của `multipart/form-data`. Không nhận file upload trực tiếp; file upload đi qua PHP.

| Tham số | Giá trị |
| --- | --- |
| `verification_file` | URL HTTP/HTTPS hoặc đường dẫn file local; ảnh lưới 3×3 |
| `input_file` | URL HTTP/HTTPS hoặc đường dẫn file local; ảnh cần xác minh |

Đường dẫn tương đối được tính từ thư mục chứa `server.py`.

```sh
curl http://127.0.0.1:5100/face_id_verification \
  -H 'Content-Type: application/json' \
  -d '{"verification_file":"/path/to/reference-grid.jpg","input_file":"/path/to/face.jpg"}'
```

Thành công, HTTP 200:

```json
{"status":"ok","result":0.9}
```

Thất bại:

```json
{"status":"error","message":"Không tìm thấy khuôn mặt trong ảnh đầu vào."}
```

Lỗi tham số/ảnh trả HTTP 400; lỗi xử lý khác trả HTTP 500. Route POST không tồn tại trả HTTP 404.

### Cache và file tạm

- Ảnh mẫu từ URL được lưu tại `cache/<SHA-256 của URL>`. Nếu file đã có, server dùng lại, không tải lại. Nếu nội dung ảnh thay đổi nhưng URL giữ nguyên, cần xóa file cache tương ứng hoặc dùng URL mới.
- Ảnh đầu vào từ URL luôn được tải vào `temp/request-.../`, rồi xóa thư mục request sau xử lý, kể cả khi lỗi.
- File local không bị Python xóa.
- Mỗi ảnh tải từ URL tối đa 20 MiB; timeout đọc mạng là 30 giây. POST body tối đa 1 MiB.
- Các request xác minh được xử lý lần lượt bằng lock để dùng chung model và hạn chế CPU/RAM. `compare()` tính thời gian đọc/xử lý ảnh sau khi nạp model; API hiện chỉ trả điểm, không trả thời gian.

## Chi tiết xử lý PHP

File upload phải là ảnh, tối đa 20 MiB, được lưu tại `temp/php-.../input_image.bin`. PHP truyền đường dẫn tuyệt đối cho Python và dọn file/thư mục request trong `finally`. Giới hạn thực tế còn phụ thuộc `upload_max_filesize`, `post_max_size` của PHP và cấu hình web server.

PHP giữ nguyên body và HTTP status từ Python. Nếu gọi cURL thất bại hoặc có lỗi nội bộ PHP, trả HTTP 503 với chi tiết trong `message`:

```json
{"status":"error","message":"Service error: ... cURL error 7: Failed to connect ..."}
```

Timeout kết nối Python là 3 giây; timeout toàn bộ lời gọi là 300 giây. Phương thức khác POST trả HTTP 405; tham số không hợp lệ trả HTTP 400.

## Upload từ Mac

Cài công cụ cần thiết:

```bash
brew install fswatch
```

Mac cần có `rsync`, quyền SSH tới máy đích và cấu hình `UPLOAD_DEST` trong file cấu hình local mà script yêu cầu. Giá trị có dạng `user@host:/absolute/project/path/`. Dùng SSH key để tránh nhập mật khẩu sau mỗi thay đổi. Thư mục đích phải tồn tại và user SSH có quyền ghi.

Upload một lần:

```bash
bash scripts/upload_init.sh
```

Theo dõi thay đổi và tự upload:

```bash
bash scripts/upload_sync.sh
```

Nhấn `Ctrl+C` để dừng. Script sync theo dõi thay đổi phát sinh sau khi bắt đầu, nên hãy chạy init trước nếu cần upload toàn bộ bản hiện tại.

Đây là đồng bộ một chiều Mac → Ubuntu, không tải thay đổi trên server về Mac. Script không dùng `--delete`, nên file xóa trên Mac vẫn còn trên server. Cả hai script upload bị loại khỏi rsync và chỉ dùng trên Mac.

**Danh sách loại trừ rsync độc lập với `.gitignore`.** Hiện rsync loại `.git/`, `node_modules/`, các file `.env`, `.env.*` và hai script upload. Các mục khác trong `.gitignore` không tự động bị loại khỏi upload. Không có thao tác tự restart Python sau upload; cần stop/start server trên Ubuntu khi thay đổi mã Python.

## Xử lý lỗi thường gặp

### No module named cv2

Kiểm tra đúng Python của virtualenv và cài thư viện vào môi trường đó:

```sh
.venv/bin/python3 -m pip install 'opencv-python-headless>=4.10'
```

Sau đó stop/start bằng lệnh có `PATH` tới virtualenv như phần quản lý server.

### Address already in use

```sh
sudo ss -ltnp 'sport = :5100'
```

Nếu server cũ nằm trong screen, dừng bằng script với đúng user. Nếu tiến trình chạy trực tiếp, xác nhận PID rồi dùng `kill <PID>` trước khi start lại.

### Service error / cURL error 7

Kiểm tra phiên screen và chạy `curl http://127.0.0.1:5100/ping` trên Ubuntu. PHP và Python phải ở cùng máy/network namespace để gọi nhau qua `127.0.0.1`.

### Không đọc được ảnh upload hoặc không ghi được cache

Kiểm tra quyền của `cache/`, `temp/`, `models/` và các thư mục cha. File PHP upload được tạo với quyền `0600`, thư mục request là `0700`, nên chạy Python cùng user PHP, thường là `www-data`.
