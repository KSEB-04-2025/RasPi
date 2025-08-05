import serial
import io
import time
import requests
import cv2
import threading
from serial.serialutil import SerialException
from google.cloud import storage

# ─────────────────────────────
# 기본 설정
PORT = '/dev/ttyACM0'               # Arduino와 연결된 시리얼 포트
BAUD = 9600                         # 시리얼 통신 속도

SNAP1_KEYWORD = "SNAP1"             # 결함 검사 트리거 신호
SNAP2_KEYWORD = "SNAP2"             # 등급 검사 트리거 신호

URL_SNAP1 = 'http://34.64.178.127:8000/defect'     # 결함 판단 AI 서버
URL_SNAP2 = 'http://34.64.178.127:8100/classify'   # 등급 판단 Rule 서버

GCS_KEY_PATH = "service-account.json"              # GCP 인증 키
BUCKET_NAME = "zezeone_images"                     # 저장할 GCS 버킷명
GCS_FOLDER_SNAP1 = "raw_defect"                    # 결함 검사 이미지 저장 경로
GCS_FOLDER_SNAP2 = "raw_grade"                     # 등급 검사 이미지 저장 경로

CAM_IR1 = 0                         # 일반 카메라 인덱스 (결함 검사용)
CAM_IR2 = 2                         # 현미경 카메라 인덱스 (등급 검사용)
RESOLUTION = (1280, 720)           # 카메라 캡처 해상도

FRONT_HEALTHCHECK_URL = 'http://<frontend-ip>/api/healthcheck'  # 프론트엔드 헬스체크 수신 URL

# ─────────────────────────────
# 시리얼 포트 열기
def open_serial():
    while True:
        try:
            ser = serial.Serial(PORT, BAUD, timeout=1)
            time.sleep(2)
            ser.reset_input_buffer()
            print(f"[*] Serial connected: {PORT}")
            return ser
        except SerialException as e:
            print("[!] Serial open failed, retrying in 3s:", e)
            time.sleep(3)

# 카메라로 이미지 캡처
def capture_image(index):
    cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
    if not cap.isOpened():
        raise RuntimeError(f"Camera {index} open failed")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, RESOLUTION[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, RESOLUTION[1])
    time.sleep(0.7)
    ok, frame = cap.read()
    cap.release()
    return frame if ok else None

# 이미지 JPEG 인코딩
def encode_jpeg(frame):
    ok, buf = cv2.imencode('.jpg', frame)
    return buf.tobytes() if ok else None

# GCS 업로드 함수
def upload_to_gcs(image_bytes, filename, folder):
    try:
        client = storage.Client.from_service_account_json(GCS_KEY_PATH)
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(f"{folder}/{filename}")
        blob.upload_from_string(image_bytes, content_type='image/jpeg')
        print(f"[GCS] Uploaded: gs://{BUCKET_NAME}/{folder}/{filename}")
        return blob.public_url
    except Exception as e:
        print("[!] GCS upload failed:", e)
        return None

# 이미지 AI 서버로 전송 후 응답 반환
def post_image_to_server(image_bytes, url, retries=3):
    for i in range(retries):
        try:
            stream = io.BytesIO(image_bytes)
            files = {'file': ('image.jpg', stream, 'image/jpeg')}
            resp = requests.post(url, files=files, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            print(f"[!] Server error {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            print(f"[!] Server request failed ({i+1}/{retries}):", e)
        time.sleep(0.5)
    return None

# SNAP1 처리 (결함 검사)
def handle_snap1(ser):
    try:
        frame = capture_image(CAM_IR1)
        image_bytes = encode_jpeg(frame)
        if not image_bytes:
            raise ValueError("JPEG encoding failed")

        ts = int(time.time())
        filename = f"ir1_{ts}.jpg"

        if not upload_to_gcs(image_bytes, filename, GCS_FOLDER_SNAP1):
            ser.write(b"GO\n")
            return

        result = post_image_to_server(image_bytes, URL_SNAP1)
        label = result.get("label") if result else None

        if label == "X":
            ser.write(b"X\n")
            print("[SNAP1] Defect → sent: X")
        else:
            ser.write(b"GO\n")
            print("[SNAP1] Normal → sent: GO")
    except Exception as e:
        print("[!] SNAP1 error:", e)
        ser.write(b"GO\n")

# SNAP2 처리 (등급 판별)
def handle_snap2(ser):
    try:
        frame = capture_image(CAM_IR2)
        image_bytes = encode_jpeg(frame)
        if not image_bytes:
            raise ValueError("JPEG encoding failed")

        ts = int(time.time())
        filename = f"snap2_{ts}.jpg"

        upload_to_gcs(image_bytes, filename, GCS_FOLDER_SNAP2)

        result = post_image_to_server(image_bytes, URL_SNAP2)
        grade = result.get("label") if result else None

        if grade:
            ser.write(f"RESULT:{grade}\n".encode())
            print(f"[SNAP2] Grade → sent: RESULT:{grade}")
        else:
            ser.write(b"GO\n")
            print("[SNAP2] Grade missing → sent: GO")
    except Exception as e:
        print("[!] SNAP2 error:", e)
        ser.write(b"GO\n")

# ─────────────────────────────
# 헬스체크 기능

# 카메라 정상 작동 여부 확인
def check_camera(index):
    try:
        frame = capture_image(index)
        return "ok" if frame is not None else "fail"
    except Exception:
        return "fail"

# 서버 응답 상태 확인
def check_server_health(url):
    try:
        resp = requests.get(url, timeout=3)
        return "ok" if resp.status_code == 200 else "fail"
    except Exception:
        return "fail"

# 헬스 상태 프론트엔드 서버로 전송
def report_health_to_frontend():
    status = {
        "camera1": check_camera(CAM_IR1),
        "camera2": check_camera(CAM_IR2),
        "defect_server": check_server_health("http://34.64.178.127:8000/health"),
        "classify_server": check_server_health("http://34.64.178.127:8100/health"),
    }
    status["overall"] = "ok" if all(v == "ok" for v in status.values()) else "fail"

    try:
        resp = requests.post(FRONT_HEALTHCHECK_URL, json=status, timeout=5)
        print("[HealthCheck] Sent:", status, "| Response:", resp.status_code)
    except Exception as e:
        print("[!] HealthCheck send failed:", e)

# 1분 주기로 헬스체크 반복 실행
def start_healthcheck_loop():
    def loop():
        while True:
            report_health_to_frontend()
            time.sleep(60)
    threading.Thread(target=loop, daemon=True).start()

# ─────────────────────────────
# 메인 실행 루프
def main():
    ser = open_serial()
    report_health_to_frontend()
    start_healthcheck_loop()

    try:
        while True:
            line = ser.readline().decode(errors='ignore').strip()
            if not line:
                continue
            print("[ARDUINO]", line)

            if line == SNAP1_KEYWORD:
                handle_snap1(ser)
            elif line == SNAP2_KEYWORD:
                handle_snap2(ser)

    except KeyboardInterrupt:
        print("\n[*] Stopped by user")
    except SerialException as e:
        print("[!] Serial error:", e)
    finally:
        ser.close()

# ─────────────────────────────
if __name__ == "__main__":
    main()
