import cv2
import serial  # pyserial 라이브러리 설치 필요 (pip install pyserial)
import requests # requests 라이브러리 설치 필요 (pip install requests)
import time
import os

def send_to_server(file_path, server_url):
    """
    지정된 서버 URL로 이미지 파일을 POST 방식으로 전송합니다.

    Args:
        file_path (str): 전송할 이미지 파일의 경로.
        server_url (str): 파일을 수신할 서버의 URL.
    """
    if not os.path.exists(file_path):
        print(f"오류: 서버로 전송할 파일이 없습니다: {file_path}")
        return

    try:
        with open(file_path, 'rb') as f:
            files = {'image': (os.path.basename(file_path), f, 'image/jpeg')}
            response = requests.post(server_url, files=files, timeout=10)
            response.raise_for_status()  # 2xx 응답이 아닐 경우 예외 발생
            print(f"성공: 서버로 파일을 전송했습니다. (응답: {response.status_code})")
            # 서버에서 받은 응답을 출력할 수도 있습니다.
            # print("서버 응답:", response.json())
    except requests.exceptions.RequestException as e:
        print(f"오류: 서버 전송에 실패했습니다: {e}")


def capture_image(save_path, camera_index=0):
    """
    이미지를 캡처하여 지정된 경로에 저장합니다.

    Args:
        save_path (str): 이미지를 저장할 전체 파일 경로.
        camera_index (int): 사용할 카메라의 인덱스.
    
    Returns:
        bool: 캡처 및 저장 성공 여부.
    """
    # 라즈베리파이에서는 cv2.CAP_DSHOW 옵션을 사용하지 않는 것이 더 안정적일 수 있습니다.
    cap = cv2.VideoCapture(camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920) # 프레임 너비 설정
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080) # 프레임 높이 설정

    if not cap.isOpened():
        print(f"오류: 카메라({camera_index})를 열 수 없습니다.")
        return False

    ret, frame = cap.read()
    if ret:
        cv2.imwrite(save_path, frame)
        print(f"성공: 이미지가 '{save_path}'에 저장되었습니다.")
        cap.release()
        return True
    else:
        print("오류: 이미지를 캡처하지 못했습니다.")
        cap.release()
        return False

if __name__ == "__main__":
    # --- 설정 부분 ---
    # !사용자 환경에 맞게 수정하세요!
    SERIAL_PORT = '/dev/ttyACM0'  # 라즈베리파이의 일반적인 아두이노 포트 이름
    BAUDRATE = 9600
    CAMERA_INDEX = 0
    SERVER_URL = 'http://your_server_ip:port/upload' # !AI 서버의 주소로 반드시 수정!

    # 홈 디렉토리 아래 바탕화면 경로를 자동으로 찾습니다.
    home_dir = os.path.expanduser('~')
    save_dir = os.path.join(home_dir, 'Desktop', 'captured_images')
    
    # 저장할 폴더가 없으면 생성
    os.makedirs(save_dir, exist_ok=True)
    print(f"이미지 저장 폴더: {save_dir}")
    # -----------------

    try:
        ser = serial.Serial(SERIAL_PORT, BAUDRATE)
        print(f"{SERIAL_PORT} 포트 연결 성공. 아두이노 신호를 기다립니다...")
    except serial.SerialException:
        print(f"오류: {SERIAL_PORT} 포트를 열 수 없습니다.")
        exit()

    while True:
        try:
            line = ser.readline()
            if line:
                signal = line.decode('utf-8').strip()
                if signal == "CAPTURE":
                    print("'CAPTURE' 신호 수신! 작업을 시작합니다.")
                    
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    filename = f"capture_{timestamp}.jpg"
                    file_path = os.path.join(save_dir, filename)
                    
                    # 1. 이미지 캡처 및 저장
                    if capture_image(save_path=file_path, camera_index=CAMERA_INDEX):
                        # 2. 서버로 파일 전송
                        send_to_server(file_path, SERVER_URL)

        except KeyboardInterrupt:
            print("프로그램을 종료합니다.")
            break
        except Exception as e:
            print(f"처리 중 오류 발생: {e}")
            
    if ser.is_open:
        ser.close()
        print("시리얼 포트를 닫았습니다.")
        
        
# 이 코드는 라즈베리파이에서 아두이노로부터 'CAPTURE' 신호를 수신하여 이미지를 캡처하고, 지정된 서버로 전송하는 기능을 수행합니다.
# 아두이노와의 연결, 이미지 캡처, 파일 저장 및 서버 전송을 포함합니다.
# 사용자는 자신의 환경에 맞게 SERIAL_PORT, CAMERA_INDEX, SERVER_URL 등을 수정해야 합니다.
# 또한, 서버는 파일 업로드를 처리할 수 있는 엔드포인트를 구현해야 합니다.
# 이 코드는 예외 처리를 포함하여 안정성을 높였습니다.
# 이미지 저장 경로는 사용자의 홈 디렉토리 아래 바탕화면에 'captured_images' 폴더로 설정되어 있습니다.
# 이 폴더가 없으면 자동으로 생성됩니다.       