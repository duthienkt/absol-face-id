<?php
header('Content-Type: application/json; charset=utf-8');

function sendError($message, $statusCode)
{
    http_response_code($statusCode);
    echo json_encode(['status' => 'error', 'message' => $message], JSON_UNESCAPED_UNICODE);
}

function isHttpUrl($value)
{
    return is_string($value)
        && filter_var($value, FILTER_VALIDATE_URL) !== false
        && in_array(strtolower((string) parse_url($value, PHP_URL_SCHEME)), ['http', 'https'], true);
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    header('Allow: POST');
    sendError('Chỉ hỗ trợ POST.', 405);
    exit;
}

$temporaryFile = null;
$temporaryDirectory = null;
$curl = null;

try {
    $params = $_POST;
    $contentType = strtolower(trim(explode(';', $_SERVER['CONTENT_TYPE'] ?? '')[0]));
    if ($contentType === 'application/json') {
        $params = json_decode(file_get_contents('php://input'), true);
        if (!is_array($params)) {
            throw new InvalidArgumentException('JSON body không hợp lệ.');
        }
    }

    $verificationFile = $params['verification_file'] ?? null;
    if (!isHttpUrl($verificationFile)) {
        throw new InvalidArgumentException('verification_file phải là URL http hoặc https. '.$verificationFile);
    }

    // A multipart file field named input_file takes precedence over a URL field.
    if (isset($_FILES['input_file'])) {
        $upload = $_FILES['input_file'];
        if (!isset($upload['error']) || !is_int($upload['error']) || $upload['error'] !== UPLOAD_ERR_OK) {
            throw new InvalidArgumentException('Upload input_file thất bại.');
        }
        if (!is_uploaded_file($upload['tmp_name'])) {
            throw new InvalidArgumentException('File upload không hợp lệ.');
        }
        if (filesize($upload['tmp_name']) > 20 * 1024 * 1024) {
            throw new InvalidArgumentException('input_file vượt quá 20 MB.');
        }
        if (@getimagesize($upload['tmp_name']) === false) {
            throw new InvalidArgumentException('input_file phải là file ảnh.');
        }

        $tempRoot = __DIR__ . '/temp';
        if (!is_dir($tempRoot) && !@mkdir($tempRoot, 0755, true) && !is_dir($tempRoot)) {
            throw new RuntimeException('Không tạo được thư mục temp.');
        }
        $temporaryDirectory = $tempRoot . '/php-' . bin2hex(random_bytes(16));
        if (!@mkdir($temporaryDirectory, 0700)) {
            $temporaryDirectory = null;
            throw new RuntimeException('Không tạo được thư mục upload tạm.');
        }
        // Never use the client filename or extension in the hosted directory.
        $temporaryFile = $temporaryDirectory . '/input_image.bin';
        if (!move_uploaded_file($upload['tmp_name'], $temporaryFile)) {
            throw new RuntimeException('Không lưu được file upload.');
        }
        chmod($temporaryFile, 0600);
        $inputFile = $temporaryFile;
    } else {
        $inputFile = $params['input_file'] ?? null;
        if (!isHttpUrl($inputFile)) {
            throw new InvalidArgumentException('input_file phải là URL http/https hoặc file upload.');
        }
    }

    if (!function_exists('curl_init')) {
        throw new RuntimeException('PHP cURL extension is unavailable.');
    }
    $curl = curl_init('http://127.0.0.1:5100/face_id_verification');
    if ($curl === false) {
        throw new RuntimeException('Cannot initialize cURL.');
    }
    curl_setopt_array($curl, [
        CURLOPT_POST => true,
        CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
        CURLOPT_POSTFIELDS => json_encode([
            'verification_file' => $verificationFile,
            'input_file' => $inputFile,
        ], JSON_THROW_ON_ERROR),
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_CONNECTTIMEOUT => 3,
        CURLOPT_TIMEOUT => 300,
        CURLOPT_PROXY => '',
    ]);
    $response = curl_exec($curl);
    if ($response === false) {
        throw new RuntimeException(sprintf(
            'Không gọi được Python tại http://127.0.0.1:5100/face_id_verification: cURL error %d: %s',
            curl_errno($curl),
            curl_error($curl)
        ));
    }
    $statusCode = (int) curl_getinfo($curl, CURLINFO_HTTP_CODE);
    if ($statusCode < 100 || $statusCode > 599) {
        throw new RuntimeException('Python trả về HTTP status không hợp lệ: ' . $statusCode);
    }
    http_response_code($statusCode);
    echo $response;
} catch (InvalidArgumentException $error) {
    sendError($error->getMessage(), 400);
} catch (Throwable $error) {
    sendError('Service error: ' . $error->getMessage(), 503);
} finally {
    if (is_resource($curl)) {
        curl_close($curl);
    }
    $curl = null;
    if ($temporaryFile !== null && is_file($temporaryFile)) {
        unlink($temporaryFile);
    }
    if ($temporaryDirectory !== null && is_dir($temporaryDirectory)) {
        rmdir($temporaryDirectory);
    }
}
