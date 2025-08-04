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
PORT = '/dev/ttyACM0'       # Arduino 연결 포트
BAUD = 9600                 # 시리얼 통신 속도

SNAP1_KEYWORD = "SNAP1"     # 결함 검사 트리거
SNAP2_KEYWORD = "SNAP2"     # 등급 검사 트리거

URL_SNAP1 = 'http://34.64.178.127:8000/defect'     # defect_server 주소
URL_SNAP2 = 'http://34.64.178.127:8100/classify'   # classify_server 주소

GCS_KEY_PATH = "service-account.json"              # GCP 서비스 계정 키 경로
BUCKET_NAME = "zezeone_images"                     # Google Cloud Storage 버킷 이름
GCS_FOLDER_SNAP1 = "raw_defect"                    # SNAP1 결과 저장 폴더
GCS_FOLDER_SNAP2 = "raw_grade"                     # SNAP2 결과 저장 폴더

CAM_IR1 = 0                                         # 일반 카메라
CAM_IR2 = 2                                         # 현미경 카메라
RESOLUTION = (1280, 720)                           # 캡처 해상도

SPRING_HEALTHCHECK_URL = 'http://<spring-server-ip>/api/healthcheck'  # Spring 서버 헬스체크 수신 엔드포인트

# ─────────────────────────────
# 시리얼 포트 연결
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

# USB 카메라 이미지 캡처
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

# JPEG 이미지 인코딩
def encode_jpeg(frame):
    ok, buf = cv2.imencode('.jpg', frame)
    return buf.tobytes() if ok else None

# GCS 업로드
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

# AI 서버 or Rule 서버로 이미지 전송
def post_image_to_server(image_bytes, url, retries=3):
    for i in range(retries):
        try:
            stream = io.BytesIO(image_bytes)
            files = {'file': ('image.jpg', stream, 'image/jpeg')}
            resp = requests.post(url, files=files, params={'return_type': 'json'}, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            print(f"[!] Server error {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            print(f"[!] Server request failed ({i+1}/{retries}):", e)
        time.sleep(0.5)
    return None

# SNAP1: 결함 검사 처리
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

# SNAP2: 등급 판별 처리
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

# 헬스체크: 카메라 상태 확인
def check_camera(index):
    try:
        frame = capture_image(index)
        return "ok" if frame is not None else "fail"
    except Exception as e:
        print(f"[!] Camera{index} error:", e)
        return "fail"

# 헬스체크: GCS 업로드/삭제 테스트
def check_gcs():
    try:
        dummy = b"health-check"
        ts = int(time.time())
        filename = f"health_check_{ts}.txt"
        client = storage.Client.from_service_account_json(GCS_KEY_PATH)
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(f"health_check/{filename}")
        blob.upload_from_string(dummy, content_type='text/plain')
        blob.delete()
        print(f"[GCS] Health check OK: {filename}")
        return "ok"
    except Exception as e:
        print("[!] GCS health check failed:", e)
        return "fail"

# 헬스체크: 서버 핑 테스트
def check_server_ping(url):
    try:
        resp = requests.get(url, timeout=3)
        return "ok" if resp.status_code == 200 else "fail"
    except Exception as e:
        print("[!] Server ping failed:", e)
        return "fail"

# 헬스체크: 모든 상태 수집 및 스프링 서버로 전송
def report_health_to_spring():
    status = {
        "camera1": check_camera(CAM_IR1),
        "camera2": check_camera(CAM_IR2),
        "gcs": check_gcs(),
        "defect_server": check_server_ping("http://34.64.178.127:8000/ping"),
        "classify_server": check_server_ping("http://34.64.178.127:8100/ping"),
    }
    status["overall"] = "ok" if all(v == "ok" for v in status.values()) else "fail"

    try:
        resp = requests.post(SPRING_HEALTHCHECK_URL, json=status, timeout=5)
        print("[HealthCheck] Sent:", status, "| Response:", resp.status_code)
    except Exception as e:
        print("[!] Failed to report health to Spring:", e)

# 헬스체크 스레드 실행 (1분 주기)
def start_healthcheck_loop():
    def loop():
        while True:
            report_health_to_spring()
            time.sleep(60)
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()

# 메인 루프: Arduino 신호 수신 후 분기
def main():
    ser = open_serial()
    report_health_to_spring()
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
