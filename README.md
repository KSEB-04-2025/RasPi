import cv2
import os
import time

def capture_image(save_path, camera_index=0):
    """
    이미지를 캡처하여 지정된 경로에 저장합니다.

    Args:
        save_path (str): 이미지를 저장할 전체 파일 경로.
        camera_index (int): 사용할 카메라의 인덱스.
    
    Returns:
        bool: 캡처 및 저장 성공 여부.
    """
    cap = cv2.VideoCapture(camera_index)
    #cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    #cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

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
    # 저장 폴더 설정
    home_dir = os.path.expanduser('~')
    save_dir = os.path.join(home_dir, 'Desktop', 'captured_images')
    os.makedirs(save_dir, exist_ok=True)
    print(f"이미지 저장 폴더: {save_dir}")

    # 저장 파일 경로 생성
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"capture_{timestamp}.jpg"
    file_path = os.path.join(save_dir, filename)

    # 이미지 캡처 테스트
    capture_image(save_path=file_path, camera_index=0)
