from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs
from urllib.request import urlopen
from pathlib import Path
from tempfile import TemporaryDirectory, NamedTemporaryFile
from threading import Lock
from email.parser import BytesParser
from email.policy import default
import hashlib
import json

import sys
from time import perf_counter


BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "cache"
TEMP_DIR = BASE_DIR / "temp"
MAX_DOWNLOAD_SIZE = 20 * 1024 * 1024
VERIFICATION_LOCK = Lock()
MODELS = None


def model_path(folder, filename):
    path = BASE_DIR / "models" / filename
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/{folder}/{filename}"
        print(f"Downloading {filename}...", file=sys.stderr)
        with urlopen(url, timeout=120) as response:
            data = response.read()
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(data)
        temporary.replace(path)
    return str(path)


def load_models():
    import cv2 as cv

    cv.setNumThreads(2)
    detector = cv.FaceDetectorYN.create(
        model_path("face_detection_yunet", "face_detection_yunet_2023mar.onnx"),
        "", (320, 320), 0.8,
    )
    recognizer = cv.FaceRecognizerSF.create(
        model_path("face_recognition_sface", "face_recognition_sface_2021dec.onnx"),
        "",
    )
    return detector, recognizer


def compare(verification_file_path, input_file_path, models=None):
    import cv2 as cv

    detector, recognizer = models if models is not None else load_models()

    # Exclude Python/OpenCV startup, model download and model loading.
    start_time = perf_counter()
    reference = cv.imread(str(verification_file_path))
    query = cv.imread(str(input_file_path))
    if reference is None or query is None:
        raise ValueError("Không đọc được ảnh mẫu hoặc ảnh đầu vào.")
    height, width = reference.shape[:2]
    if height < 3 or width < 3:
        raise ValueError("Ảnh mẫu quá nhỏ để chia lưới 3x3.")

    def feature(image):
        # Resize each individual image, preserving its aspect ratio.
        h, w = image.shape[:2]
        scale = min(640 / max(h, w), 320 / min(h, w))
        image = cv.resize(image, (max(1, round(w * scale)), max(1, round(h * scale))))
        detector.setInputSize((image.shape[1], image.shape[0]))
        _, faces = detector.detect(image)
        if faces is None or len(faces) == 0:
            return None
        largest_face = max(faces, key=lambda face: float(face[2]) * float(face[3]))
        aligned = recognizer.alignCrop(image, largest_face)
        return recognizer.feature(aligned)

    query_feature = feature(query)
    if query_feature is None:
        raise ValueError("Không tìm thấy khuôn mặt trong ảnh đầu vào.")

    scores = []
    for row in range(3):
        for column in range(3):
            cell = reference[
                row * height // 3:(row + 1) * height // 3,
                column * width // 3:(column + 1) * width // 3,
            ]
            reference_feature = feature(cell)
            if reference_feature is not None:
                scores.append(recognizer.match(
                    reference_feature, query_feature, cv.FaceRecognizerSF_FR_COSINE,
                ))

    if not scores:
        raise ValueError("Không tìm thấy khuôn mặt trong 9 ô ảnh mẫu.")
    score = max(-1.0, min(1.0, max(scores)))
    elapsed = perf_counter() - start_time
    return score, elapsed



def download(url, destination):
    # Atomic replacement prevents incomplete downloads being reused as cache.
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with NamedTemporaryFile(dir=destination.parent, delete=False) as output:
            temporary = Path(output.name)
            with urlopen(url, timeout=30) as response:
                if urlsplit(response.geturl()).scheme not in ("http", "https"):
                    raise ValueError("URL tải ảnh phải dùng http hoặc https.")
                total = 0
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_DOWNLOAD_SIZE:
                        raise ValueError("Ảnh tải về vượt quá 20 MB.")
                    output.write(chunk)
        temporary.replace(destination)
    finally:
        if "temporary" in locals():
            temporary.unlink(missing_ok=True)


def resolve_file(value, *, verification, temp_directory):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("verification_file và input_file phải là chuỗi không rỗng.")
    parsed = urlsplit(value)
    if parsed.scheme.lower() in ("http", "https"):
        if not parsed.hostname:
            raise ValueError("URL ảnh không hợp lệ.")
        if verification:
            destination = CACHE_DIR / hashlib.sha256(value.encode("utf-8")).hexdigest()
            if not destination.is_file():
                download(value, destination)
        else:
            destination = Path(temp_directory) / "input_image"
            download(value, destination)
        return destination
    if parsed.scheme:
        raise ValueError("Chỉ hỗ trợ URL http/https hoặc đường dẫn file trong máy.")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    if not path.is_file():
        raise ValueError(f"Không tìm thấy file: {value}")
    return path


def verify_face(params):
    global MODELS
    # Serialize inference to protect mutable OpenCV models and limit CPU/RAM use.
    with VERIFICATION_LOCK:
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix="request-", dir=TEMP_DIR) as temp_directory:
            verification = resolve_file(params.get("verification_file"), verification=True,
                                        temp_directory=temp_directory)
            input_image = resolve_file(params.get("input_file"), verification=False,
                                       temp_directory=temp_directory)
            if MODELS is None:
                MODELS = load_models()
            score, _ = compare(verification, input_image, models=MODELS)
            return float(score)


class RequestHandler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_params(self):
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= 1024 * 1024:
            raise ValueError("POST body phải có dữ liệu và không vượt quá 1 MB.")
        body = self.rfile.read(length)
        content_type = self.headers.get("Content-Type", "")
        media_type = content_type.split(";", 1)[0].strip().lower()
        if media_type == "application/json":
            params = json.loads(body)
            if not isinstance(params, dict):
                raise ValueError("JSON body phải là một object.")
            return params
        if media_type == "application/x-www-form-urlencoded":
            return {key: values[-1] for key, values in
                    parse_qs(body.decode("utf-8"), keep_blank_values=True).items()}
        if media_type == "multipart/form-data":
            message = BytesParser(policy=default).parsebytes(
                f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode() + body
            )
            if not message.is_multipart():
                raise ValueError("Multipart body không hợp lệ.")
            params = {}
            for part in message.iter_parts():
                name = part.get_param("name", header="content-disposition")
                if name:
                    if part.get_filename() is not None:
                        raise ValueError("Hãy gửi URL hoặc đường dẫn, không gửi file upload.")
                    params[name] = part.get_payload(decode=True).decode("utf-8")
            return params
        raise ValueError("Dùng application/json, form-urlencoded hoặc multipart/form-data.")

    def do_POST(self):
        if urlsplit(self.path).path != "/face_id_verification":
            self.send_json(404, {"status": "error", "message": "Route không tồn tại."})
            return
        try:
            params = self.read_params()
            result = verify_face(params)
        except (ValueError, UnicodeError) as error:
            self.send_json(400, {"status": "error", "message": str(error)})
        except Exception as error:
            self.send_json(500, {"status": "error", "message": str(error)})
        else:
            self.send_json(200, {"status": "ok", "result": result})

    def do_GET(self):
        if urlsplit(self.path).path == "/ping":
            body = b"pong"
            self.send_response(200)
        else:
            body = b"Not Found"
            self.send_response(404)

        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    with ThreadingHTTPServer(("127.0.0.1", 5100), RequestHandler) as server:
        print("Server listening on http://127.0.0.1:5100", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
