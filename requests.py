import cv2
import os
import time
import serial
import requests  # 이미지 전송용

def capture_image(save_path, camera_index=0):
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"오류: 카메라({camera_index})를 열 수 없습니다.")
        return False

    ret, frame = cap.read()
    if ret:
        cv2.imwrite(save_path, frame)
        print(f"📸 성공: 이미지 저장 완료 → {save_path}")
        cap.release()
        return True
    else:
        print("❌ 오류: 이미지 캡처 실패")
        cap.release()
        return False

def send_image_to_server(file_path, server_url):
    try:
        with open(file_path, 'rb') as img_file:
            files = {'file': (os.path.basename(file_path), img_file, 'image/jpeg')}
            response = requests.post(server_url, files=files)
            response.raise_for_status()
            print(f"✅ 서버 전송 완료 → 응답: {response.json()}")
    except Exception as e:
        print(f"❌ 서버 전송 실패: {e}")

# 시작
if __name__ == "__main__":
    home_dir = os.path.expanduser('~')
    save_dir = os.path.join(home_dir, 'Desktop', 'captured_images')
    os.makedirs(save_dir, exist_ok=True)

    SERVER_URL = 'http://34.64.123.85:8080/upload/'  # ← 반드시 본인의 서버 IP로 바꾸세요!

    try:
        ser = serial.Serial('/dev/ttyACM0', 9600)
        print("✅ 아두이노 연결 성공. 신호 대기 중...")
    except serial.SerialException as e:
        print("❌ Serial 연결 실패:", e)
        exit()

    while True:
        try:
            if ser.in_waiting:
                line = ser.readline().decode().strip()
                print("📥 수신된 신호:", line)

                if line == "CAPTURE":
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    filename = f"capture_{timestamp}.jpg"
                    file_path = os.path.join(save_dir, filename)

                    if capture_image(file_path):
                        send_image_to_server(file_path, SERVER_URL)

        except KeyboardInterrupt:
            print("🔌 종료")
            break
        except Exception as e:
            print(f"❌ 처리 중 오류: {e}")

    ser.close()
