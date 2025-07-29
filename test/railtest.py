import serial, io, time, requests, cv2

PORT = '/dev/ttyACM0'
BAUD = 9600
URL  = 'http://34.64.178.127:8100/classify'

# -------- 카메라 매핑 --------
# 센서1 → 카메라 인덱스 (예: 0)
# 센서2 → 카메라 인덱스 (예: 1)
# 필요하면 0/1 바꿔주세요.
CAM_FOR_SNAP1 = 0
CAM_FOR_SNAP2 = 1
# 또는 '/dev/v4l/by-id/...' 같은 고정 경로로 바꿔도 됨

def capture_usbcam(cam_idx_or_path):
    print(f"[*] USB카메라({cam_idx_or_path}) 촬영")
    cap = cv2.VideoCapture(cam_idx_or_path)
    if not cap.isOpened():
        raise RuntimeError(f"USB카메라 {cam_idx_or_path} 오픈 실패")
    time.sleep(2)  # 웜업
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise RuntimeError(f"USB카메라 {cam_idx_or_path} 촬영 실패")
    return frame

def upload_image(frame):
    ok, jpg_buf = cv2.imencode('.jpg', frame)
    if not ok:
        print("[!] JPEG 인코딩 실패")
        return None

    stream = io.BytesIO(jpg_buf.tobytes())
    stream.seek(0)
    files = {'file': ('image.jpg', stream, 'image/jpeg')}

    try:
        resp = requests.post(URL, files=files, params={'return_type':'json'})
        resp.raise_for_status()
        data = resp.json()
        grade = data.get('label')
        print("[+] 판정 결과:", grade)
        return grade
    except Exception as e:
        print("[!] 서버 통신 실패:", e)
        return None

def main():
    ser = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(2)
    ser.reset_input_buffer()

    while True:
        raw = ser.readline()
        if not raw:
            continue
        line = raw.decode(errors='ignore').strip()
        if not line:
            continue

        print("아두이노:", line)

        if line == "SNAP1":
            # 센서1 → 촬영만
            try:
                frame = capture_usbcam(CAM_FOR_SNAP1)
                # 필요하면 저장만
                # cv2.imwrite("snap1.jpg", frame)
            except Exception as e:
                print("[!] SNAP1 촬영 실패:", e)
                # 아두이노는 자체적으로 재가동하므로 별도 명령 안 보내도 됨
                # 필요시: ser.write(b"GO\n")

        elif line == "SNAP2":
            # 센서2 → 촬영 + 서버 업로드
            try:
                frame = capture_usbcam(CAM_FOR_SNAP2)
                grade = upload_image(frame)
            except Exception as e:
                print("[!] SNAP2 촬영 실패:", e)
                grade = None

            if grade is not None:
                ser.write(f"RESULT:{grade}\n".encode())
            else:
                ser.write(b"GO\n")  # 실패 시에도 레일은 돌려야 한다면

if __name__ == "__main__":
    main()
