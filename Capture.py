import os
import time
import serial
import requests

# ───────────────────────────────
# ✅ 사용자 환경 설정
# ───────────────────────────────
SERIAL_PORT = '/dev/ttyACM0'  # 아두이노 A (칸막이 제어용)
BAUDRATE = 9600
SERVER_URL = 'http://<AI_SERVER_IP>:<PORT>/predict'  # AI 서버 주소로 수정
DELETE_IMAGE_AFTER_SEND = True

# 사진 저장 경로
home_dir = os.path.expanduser('~')
save_dir = os.path.join(home_dir, 'Desktop', 'captured_images')
os.makedirs(save_dir, exist_ok=True)


# ───────────────────────────────
# ✅ 1. fswebcam으로 사진 촬영
# ───────────────────────────────
def capture_image(save_path):
    result = os.system(f"fswebcam -r 1280x720 --no-banner {save_path}")
    if result == 0 and os.path.exists(save_path):
        print(f"📷 이미지 저장 성공: {save_path}")
        return True
    else:
        print("❌ 이미지 촬영 실패")
        return False


# ───────────────────────────────
# ✅ 2. AI 서버로 이미지 전송 및 판정 수신
# ───────────────────────────────
def send_to_server(file_path, server_url):
    try:
        with open(file_path, 'rb') as f:
            files = {'image': (os.path.basename(file_path), f, 'image/jpeg')}
            response = requests.post(server_url, files=files, timeout=10)
            response.raise_for_status()
            result = response.json()  # {"result": "A"}
            print(f"📩 AI 판정 결과 수신: {result}")
            return result
    except Exception as e:
        print(f"❌ 서버 통신 오류: {e}")
        return None


# ───────────────────────────────
# ✅ 3. 결과를 아두이노로 전송
# ───────────────────────────────
def send_result_to_arduino(ser, result_value):
    if result_value in ['A', 'B']:
        ser.write(result_value.encode('utf-8'))
        print(f"📤 결과 '{result_value}' 아두이노로 전송 완료")
    else:
        print(f"⚠ 알 수 없는 결과 '{result_value}', 전송 생략")


# ───────────────────────────────
# ✅ 4. 메인 루프
# ───────────────────────────────
def main():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUDRATE)
        print(f"🔌 아두이노 포트 {SERIAL_PORT} 연결됨. 센서 신호 대기 중...")

        while True:
            line = ser.readline()
            if line:
                signal = line.decode('utf-8').strip()
                if signal == "TRIGGER":
                    print("\n📥 센서 감지 신호 수신 → 프로세스 시작")

                    # 1. 컨베이어 정지는 아두이노에서 자동 처리
                    # 2. 이미지 촬영
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    filename = f"capture_{timestamp}.jpg"
                    file_path = os.path.join(save_dir, filename)

                    if not capture_image(file_path):
                        continue

                    # 3. AI 서버로 전송 및 결과 수신
                    result_json = send_to_server(file_path, SERVER_URL)
                    if result_json and "result" in result_json:
                        result = result_json["result"]
                        send_result_to_arduino(ser, result)
                    else:
                        print("❗ AI 서버에서 유효한 결과를 받지 못했습니다")

                    # 4. 전송 완료된 이미지 삭제
                    if DELETE_IMAGE_AFTER_SEND and os.path.exists(file_path):
                        os.remove(file_path)
                        print(f"🗑 이미지 삭제 완료: {file_path}")

                    print("✅ 처리 완료. 다음 감지를 대기 중...")

    except serial.SerialException:
        print(f"❌ 시리얼 포트 {SERIAL_PORT} 연결 실패")
    except KeyboardInterrupt:
        print("\n🛑 수동 종료됨")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("🔒 시리얼 포트 닫힘")


# ───────────────────────────────
# ✅ 프로그램 시작
# ───────────────────────────────
if __name__ == "__main__":
    main()
