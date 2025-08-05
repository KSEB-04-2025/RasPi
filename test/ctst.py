import cv2
import io
import time
import requests
from pathlib import Path

# 설정값
CAM_INDEX = 0              # 실제 사용하는 USB 카메라 번호 (ex: 0, 2 등)
IMG_SIZE = (720, 720)      # 캡처 해상도 (W, H)
CROP_SIZE = (360, 280)     # 저장·업로드용 크롭 해상도 (W, H, 가운데)
TEST_DIR = Path("./test_snaps")  # 저장 폴더
SERVER_URL = "http://34.64.178.127:8000/defect"
RET_TYPE = "json"

def crop_center(img, size=(360, 360), enforce=True):
    """가운데 기준으로 size(W,H)만큼 크롭. enforce=True면 최종 크기를 강제."""
    h, w = img.shape[:2]
    cw, ch = size
    cw = min(cw, w); ch = min(ch, h)
    x1 = max((w - cw) // 2, 0)
    y1 = max((h - ch) // 2, 0)
    cropped = img[y1:y1+ch, x1:x1+cw]
    if enforce and (cropped.shape[1] != size[0] or cropped.shape[0] != size[1]):
        cropped = cv2.resize(cropped, size, interpolation=cv2.INTER_AREA)
    return cropped

def capture_and_save(index=CAM_INDEX, size=IMG_SIZE, crop_size=CROP_SIZE, test_dir=TEST_DIR):
    test_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
    if not cap.isOpened():
        print(f"[!] {time.strftime('%Y-%m-%d %H:%M:%S')} 카메라 오픈 실패 | index={index}")
        return None

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  size[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, size[1])
    time.sleep(0.7)

    ok, frame = cap.read()
    cap.release()
    if not ok:
        print(f"[!] {time.strftime('%Y-%m-%d %H:%M:%S')} 캡처 실패 | index={index}")
        return None

    # --- 가운데 360x360 크롭 ---
    if crop_size:
        frame = crop_center(frame, crop_size, enforce=True)

    ts = time.strftime("%Y%m%d_%H%M%S")
    filename = f"test_{ts}.jpg"
    save_path = test_dir / filename
    cv2.imwrite(str(save_path), frame)
    print(f"[{ts}] 이미지 저장 완료 | {save_path} | size={frame.shape[1]}x{frame.shape[0]}")
    return save_path

def upload_and_log(img_path):
    try:
        with open(img_path, "rb") as f:
            files = {'file': (img_path.name, f, 'image/jpeg')}
            resp = requests.post(SERVER_URL, files=files, params={'return_type': RET_TYPE}, timeout=5)
            now = time.strftime('%Y-%m-%d %H:%M:%S')
            if resp.status_code == 200:
                resp_json = resp.json()
                label = resp_json.get("label", "None")
                print(f"[{now}] {img_path.name} | 응답코드={resp.status_code} | label={label} | 전체={resp_json}")
            else:
                print(f"[{now}] {img_path.name} | 응답코드={resp.status_code} | 서버에러: {resp.text[:200]}")
    except Exception as e:
        now = time.strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{now}] {img_path.name} | 서버 요청 실패: {e}")

if __name__ == "__main__":
    img_path = capture_and_save()
    if img_path:
        upload_and_log(img_path)
