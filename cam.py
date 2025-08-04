import serial
import io
import time
import requests
import cv2
from serial.serialutil import SerialException
from google.cloud import storage

# ─────────────────────────────
# 기본 설정
PORT = '/dev/ttyACM0'       # Arduino와 연결된 포트
BAUD = 9600                 # 시리얼 통신 속도

SNAP1_KEYWORD = "SNAP1"     # 1번 센서 감지 신호
SNAP2_KEYWORD = "SNAP2"     # 2번 센서 감지 신호

URL_SNAP1 = 'http://34.64.178.127:8000/defect'     # 결함 판별 서버
URL_SNAP2 = 'http://34.64.178.127:8100/classify'   # 등급 분류 서버

GCS_KEY_PATH = "service-account.json"              # GCP 인증키 경로
BUCKET_NAME = "zezeone_images"                     # GCS 버킷 이름
GCS_FOLDER_SNAP1 = "raw_defect"                    # SNAP1 저장 폴더
GCS_FOLDER_SNAP2 = "raw_grade"                     # SNAP2 저장 폴더

CAM_IR1 = 0   # SNAP1 카메라 인덱스
CAM_IR2 = 2   # SNAP2 카메라 인덱스
RESOLUTION = (1280, 720)  # 카메라 해상도

# ─────────────────────────────
# 시리얼 연결
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

# USB 카메라 캡처
def capture_image(index):
    cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
    if not cap.isOpened():
        raise RuntimeError(f"Camera {index} open failed")

    w, h = RESOLUTION
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
    time.sleep(0.7)  # 카메라 워밍업

    ok, frame = cap.read()
    cap.release()
    return frame if ok else None

# 이미지 JPEG 인코딩
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

# 이미지 서버에 POST 요청
def post_image_to_server(image_bytes, url, retries=3):
    for i in range(retries):
        try:
            stream = io.BytesIO(image_bytes)
            stream.seek(0)
            files = {'file': ('image.jpg', stream, 'image/jpeg')}
            resp = requests.post(url, files=files, params={'return_type': 'json'}, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            print(f"[!] Server error {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            print(f"[!] Server request failed ({i+1}/{retries}):", e)
        time.sleep(0.5)
    return None

# ─────────────────────────────
# SNAP1 처리: 결함 여부 판단
def handle_snap1(ser):
    try:
        frame = capture_image(CAM_IR1)
        image_bytes = encode_jpeg(frame)
        if not image_bytes:
            raise ValueError("JPEG encoding failed")

        ts = int(time.time())
        filename = f"ir1_{ts}.jpg"

        # GCS 업로드
        if not upload_to_gcs(image_bytes, filename, GCS_FOLDER_SNAP1):
            ser.write(b"GO\n")
            return

        # 서버 분석 요청
        result = post_image_to_server(image_bytes, URL_SNAP1)
        label = result.get("label") if result else None

        # 결함일 경우 X, 아니면 GO
        if label == "X":
            ser.write(b"X\n")
            print("[SNAP1] Defect → sent: X")
        else:
            ser.write(b"GO\n")
            print("[SNAP1] Normal → sent: GO")

    except Exception as e:
        print("[!] SNAP1 error:", e)
        ser.write(b"GO\n")

# SNAP2 처리: 품질 등급 판단
def handle_snap2(ser):
    try:
        frame = capture_image(CAM_IR2)
        image_bytes = encode_jpeg(frame)
        if not image_bytes:
            raise ValueError("JPEG encoding failed")

        ts = int(time.time())
        filename = f"snap2_{ts}.jpg"

        # GCS 업로드
        upload_to_gcs(image_bytes, filename, GCS_FOLDER_SNAP2)

        # 서버 분석 요청
        result = post_image_to_server(image_bytes, URL_SNAP2)
        grade = result.get("label") if result else None

        # 등급이 존재하면 전송, 없으면 GO
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
# 메인 루프: 시리얼 신호 수신 및 분기 처리
def main():
    ser = open_serial()
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
