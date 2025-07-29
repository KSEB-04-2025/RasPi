import serial
import io
import time
import requests
import cv2
from picamera2 import Picamera2
from serial.serialutil import SerialException
from google.cloud import storage

# ─────────────────────────────
# 기본 설정
PORT = '/dev/ttyACM0'
BAUD = 9600
SNAP_KEYWORD = "SNAP2"
URL  = 'http://34.64.178.127:8100/classify'

# GCS 설정
GCS_KEY_PATH = "service-account.json"
BUCKET_NAME = "zezeone_images"
GCS_FOLDER = "raw_grade"

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

# ─────────────────────────────
def upload_to_gcs(image_bytes, filename):
    try:
        client = storage.Client.from_service_account_json(GCS_KEY_PATH)
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(f"{GCS_FOLDER}/{filename}")
        blob.upload_from_string(image_bytes, content_type='image/jpeg')
        # blob.make_public()
        print(f"[+] GCS 업로드 완료: {blob.public_url}")
        return blob.public_url
    except Exception as e:
        print("[!] GCS 업로드 실패:", e)
        return None

# ─────────────────────────────
def take_and_upload():
    print("[*] 사진 촬영 및 전송 시작")

    # 카메라 준비 및 캡처
    picam = Picamera2()
    preview_config = picam.create_preview_configuration(main={"size": (640, 480)})
    picam.configure(preview_config)
    picam.start()
    time.sleep(2)  # 노출 안정화
    frame = picam.capture_array()
    picam.close()

    # JPEG 인코딩
    ok, jpg_buf = cv2.imencode('.jpg', frame)
    if not ok:
        print("[!] JPEG 인코딩 실패")
        return None

    image_bytes = jpg_buf.tobytes()

    # GCS 업로드
    timestamp = int(time.time())
    filename = f"micro_{timestamp}.jpg"
    gcs_url = upload_to_gcs(image_bytes, filename)

    # 서버 전송 (파일 전송 유지)
    try:
        stream = io.BytesIO(image_bytes)
        stream.seek(0)
        files = {'file': ('image.jpg', stream, 'image/jpeg')}
        resp = requests.post(URL, files=files, params={'return_type': 'json'})
        resp.raise_for_status()
        data = resp.json()
        grade = data.get('label')
        print("[+] 판정 결과:", grade)
        return grade
    except Exception as e:
        print("[!] 서버 통신 실패:", e)
        return None

# ─────────────────────────────
def main():
    ser = open_serial()
    while True:
        try:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode(errors='ignore').strip()
            if not line:
                continue
            print("아두이노:", line)

            if line == SNAP_KEYWORD:
                grade = take_and_upload()
                if grade is None:
                    ser.write(b"GO\n")  # 실패 시에도 재가동 명령
                else:
                    msg = f"RESULT:{grade}\n".encode()
                    ser.write(msg)

        except SerialException as e:
            print("[!] 시리얼 통신 오류:", e)
            ser.close()
            ser = open_serial()
        except KeyboardInterrupt:
            print("\n[*] 종료")
            ser.close()
            break

# ─────────────────────────────
if __name__ == "__main__":
    main()
