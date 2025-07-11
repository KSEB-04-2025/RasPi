import cv2
import os
import time
import serial
import requests

def capture_image(save_path, camera_index=0):
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print("❌ 카메라 열기 실패")
        return False

    ret, frame = cap.read()
    cap.release()

    if ret:
        cv2.imwrite(save_path, frame)
        print(f"📸 이미지 저장 완료: {save_path}")
        return True
    else:
        print("❌ 이미지 캡처 실패")
        return False

def send_image_to_server(file_path, server_url):
    try:
        with open(file_path, 'rb') as img_file:
            files = {'file': (os.path.basename(file_path), img_file, 'image/jpeg')}
            response = requests.post(server_url, files=files)
            response.raise_for_status()
            result = response.json()
            print(f"✅ 서버 응답 수신: {result}")
            return result
    except Exception as e:
        print(f"❌ 서버 전송 실패: {e}")
        return None

# ─────────── 시작 ───────────
if __name__ == "__main__":
    home_dir = os.path.expanduser('~')
    save_dir = os.path.join(home_dir, 'Desktop', 'captured_images')
    os.makedirs(save_dir, exist_ok=True)

    SERVER_URL = 'http://<AI_SERVER_IP>:<PORT>/upload/'  # ← 반드시 본인의 서버 주소로 수정

    try:
        ser_a = serial.Serial('/dev/ttyACM0', 9600)  # 아두이노 A (칸막이 제어)
        ser_b = serial.Serial('/dev/ttyACM1', 9600)  # 아두이노 B (센서/모터)

        print("✅ 아두이노 A, B 연결 성공. 센서 신호 대기 중...")

        while True:
            if ser_b.in_waiting:
                line = ser_b.readline().decode().strip()
                print(f"📥 아두이노 B → '{line}' 수신")

                if line == "CAPTURE":
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    filename = f"capture_{timestamp}.jpg"
                    file_path = os.path.join(save_dir, filename)

                    if capture_image(file_path):
                        result = send_image_to_server(file_path, SERVER_URL)

                        if result and "result" in result:
                            value = result["result"]
                            if value in ['A', 'B']:
                                ser_a.write(value.encode('utf-8'))
                                print(f"📤 결과 '{value}' 아두이노 A로 전송 완료")
                            else:
                                print(f"⚠ 알 수 없는 판정 결과: {value}")
                        else:
                            print("❗ AI 응답 오류 또는 result 키 없음")

                        os.remove(file_path)

    except serial.SerialException as e:
        print(f"❌ 시리얼 연결 오류: {e}")
    except KeyboardInterrupt:
        print("🔌 수동 종료됨")
    finally:
        if 'ser_a' in locals() and ser_a.is_open:
            ser_a.close()
        if 'ser_b' in locals() and ser_b.is_open:
            ser_b.close()
        print("🔒 시리얼 포트 닫힘")
