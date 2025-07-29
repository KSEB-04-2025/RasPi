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

SNAP1_KEYWORD = "SNAP1"   # IR1 감지: 일반캠 → AI 서버 전송
SNAP2_KEYWORD = "SNAP2"   # IR2 감지: 현미경 → 품질 서버 + GCS 업로드

# 서버 주소 (❗여기서 AI 서버 주소 확인 필요!)
AI_SERVER_URL       = 'http://34.64.178.127:8000/upload'         # 예: http://192.168.0.100:8000/predict
CLASSIFY_SERVER_URL = 'http://34.64.178.127:8100/classify'         # 품질 분류 서버

# GCS 설정
GCS_KEY_PATH = "service-account.json"
BUCKET_NAME  = "zezeone_images"
GCS_FOLDER   = "raw_grade"

# 로컬 저장 경로 (테스트용)
SAVE_DIR_IR1 = Path("/home/root01/Arduino/Test")
SNAP1_PREFIX = "ir1"
SNAP2_PREFIX = "snap2"

# USB 카메라 인덱스
CAM_IR1 = 2   # 일반캠
CAM_IR2 = 0   # 현미경

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

def upload_to_gcs(image_bytes, filename):
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
    cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
    if not cap.isOpened():
        raise RuntimeError(f"USB 카메라 {index} 오픈 실패")

    if size:
        w, h = size
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)

    time.sleep(warmup)
    ok, frame = cap.read()
    cap.release()
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

def upload_image_to_server(image_bytes, url, retries=3):
    for i in range(retries):
        try:
            stream = io.BytesIO(image_bytes); stream.seek(0)
            files = {'file': ('image.jpg', stream, 'image/jpeg')}
            resp = requests.post(url, files=files, params={'return_type': 'json'}, timeout=5)
            if resp.status_code == 200:
                return resp.json().get('label') or resp.json().get('defect')
            else:
                print(f"[!] 서버 응답 코드 {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"[!] 업로드 실패({i+1}/{retries}):", e)
        time.sleep(0.5)
    return None

# ─────────────────────────────
def handle_snap1(ser):
    """IR1 감지: 일반캠 촬영 → 로컬 저장 + AI 서버 전송"""
    try:
        frame = capture_usbcam(CAM_IR1, size=(1280, 720))
        save_local(frame, SAVE_DIR_IR1, prefix=SNAP1_PREFIX)  # 테스트용 로컬 저장
    except Exception as e:
        print("[!] SNAP1 촬영 실패:", e)
        ser.write(b"GO\n")
        return

    ok, jpg_buf = cv2.imencode('.jpg', frame)
    if not ok:
        print("[!] JPEG 인코딩 실패")
        ser.write(b"GO\n")
        return

    image_bytes = jpg_buf.tobytes()
    defect = upload_image_to_server(image_bytes, AI_SERVER_URL)

    if defect is None:
        print("[!] 서버 응답 실패, 레일 재시작")
        ser.write(b"GO\n")
    elif defect.lower() == "true":
        print("[+] 결함 감지 → 등급 분류 생략")
        ser.write(b"GO\n")
    elif defect.lower() == "false":
        print("[+] 결함 없음 → 다음 SNAP2 대기")
    else:
        print("[!] 응답 이상 → 레일 재시작")
        ser.write(b"GO\n")

def handle_snap2(ser):
    """IR2 감지: 현미경 촬영 → GCS 업로드 + 품질 분류 서버 전송"""
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

    upload_to_gcs(image_bytes, filename)  # raw_grade 폴더 업로드
    grade = upload_image_to_server(image_bytes, CLASSIFY_SERVER_URL)

    if grade is None:
        print("[!] 품질 분류 실패")
        ser.write(b"GO\n")
    else:
        print(f"[+] 품질 분류 결과: {grade}")
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