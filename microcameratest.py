import serial
import io
import time
import requests
import cv2
import os
from pathlib import Path
from serial.serialutil import SerialException
from google.cloud import storage

# ─────────────────────────────
# 기본 설정
PORT = '/dev/ttyACM0'
BAUD = 9600

SNAP1_KEYWORD = "SNAP1"   # 1번 센서: 저장만
SNAP2_KEYWORD = "SNAP2"   # 2번 센서: 서버 업로드

URL  = 'http://34.64.178.127:8100/classify'

# GCS
GCS_KEY_PATH = "service-account.json"
BUCKET_NAME  = "zezeone_images"
GCS_FOLDER   = "raw_grade"

# 로컬 저장 경로
SAVE_DIR_IR1 = Path("/home/root01/Arduino/Test")
SNAP1_PREFIX = "ir1"
SNAP2_PREFIX = "snap2"

# USB 카메라 인덱스 매핑
CAM_IR1 = 2   # 첫 번째 센서용 (SNAP1)  -> /dev/video2
CAM_IR2 = 0   # 두 번째 센서용 (SNAP2)  -> /dev/video0

# ─────────────────────────────
def open_serial():
    while True:
        try:
            ser = serial.Serial(PORT, BAUD, timeout=1)
            time.sleep(2)
            ser.reset_input_buffer()
            print("[*] Serial Connected:", PORT)
            return ser
        except SerialException as e:
            print("[!] 시리얼 오픈 실패, 3초 후 재시도:", e)
            time.sleep(3)

def upload_to_gcs(image_bytes, filename): #gcs업로드
    try:
        client = storage.Client.from_service_account_json(GCS_KEY_PATH)
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(f"{GCS_FOLDER}/{filename}")
        blob.upload_from_string(image_bytes, content_type='image/jpeg')
        print(f"[+] GCS 업로드 완료: gs://{BUCKET_NAME}/{GCS_FOLDER}/{filename}")
        return blob.public_url
    except Exception as e:
        print("[!] GCS 업로드 실패:", e)
        return None

def capture_usbcam(index=0, warmup=0.7, size=(1280,720)):
    cap = cv2.VideoCapture(index, cv2.CAP_V4L2)   # ★ 백엔드 지정
    if not cap.isOpened():
        raise RuntimeError(f"USB 카메라 {index} 오픈 실패")

    if size:
        w, h = size
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)

    time.sleep(warmup)
    ok, frame = cap.read()
    cap.release()               # ★ 반드시 해제
    return frame if ok else None

def save_local(frame, directory: Path, prefix="snap1"):
    directory.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = directory / f"{prefix}_{ts}.jpg"
    ok = cv2.imwrite(str(path), frame)
    if ok:
        print(f"[+] 저장 완료: {path}")
        return str(path)
    else:
        print("[!] 로컬 저장 실패")
        return None

def upload_image_to_server(image_bytes, retries=3):
    for i in range(retries):
        try:
            stream = io.BytesIO(image_bytes); stream.seek(0)
            files = {'file': ('image.jpg', stream, 'image/jpeg')}
            resp = requests.post(URL, files=files, params={'return_type': 'json'}, timeout=5)
            if resp.status_code == 200:
                return resp.json().get('label')
            else:
                print(f"[!] 서버 응답 코드 {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"[!] 업로드 실패({i+1}/{retries}):", e)
        time.sleep(0.5)
    return None

def handle_snap1(ser):
    """1번 센서: USB cam2 촬영 -> 로컬 저장만"""
    try:
        frame = capture_usbcam(CAM_IR1, size=(1280, 720))
        save_local(frame, SAVE_DIR_IR1, prefix=SNAP1_PREFIX)
    except Exception as e:
        print("[!] SNAP1 처리 실패:", e)
    ser.write(b"GO\n")  # 필요 없다면 삭제

def handle_snap2(ser):
    """2번 센서: USB cam0 촬영 -> GCS + 서버 업로드"""
    try:
        frame = capture_usbcam(CAM_IR2, size=(1280, 720))
    except Exception as e:
        print("[!] SNAP2 촬영 실패:", e)
        ser.write(b"GO\n")
        return

    ok, jpg_buf = cv2.imencode('.jpg', frame)
    if not ok:
        print("[!] JPEG 인코딩 실패")
        ser.write(b"GO\n")
        return

    image_bytes = jpg_buf.tobytes()

    ts = int(time.time())
    filename = f"{SNAP2_PREFIX}_{ts}.jpg"
    upload_to_gcs(image_bytes, filename)

    grade = upload_image_to_server(image_bytes)
    if grade is None:
        ser.write(b"GO\n")
    else:
        ser.write(f"RESULT:{grade}\n".encode())

# ─────────────────────────────
def main():
    ser = open_serial()
    try:
        while True:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode(errors='ignore').strip()
            if not line:
                continue
            print("아두이노:", line)

            if line == SNAP1_KEYWORD:
                handle_snap1(ser)
            elif line == SNAP2_KEYWORD:
                handle_snap2(ser)

    except SerialException as e:
        print("[!] 시리얼 통신 오류:", e)
    except KeyboardInterrupt:
        print("\n[*] 종료")
    finally:
        ser.close()

# ─────────────────────────────
if __name__ == "__main__":
    main()
