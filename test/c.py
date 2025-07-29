#!/usr/bin/env python3
import cv2, time, io, os
from pathlib import Path

# Picamera2가 설치돼 있다면 시도
try:
    from picamera2 import Picamera2
    PICAM_AVAILABLE = True
except ImportError:
    PICAM_AVAILABLE = False

SAVE_DIR = Path("/home/root01/Arduino/Test/cam_check")
SAVE_DIR.mkdir(parents=True, exist_ok=True)

def test_opencv_cam(idx, warmup=1):
    cap = cv2.VideoCapture(idx)
    if not cap.isOpened():
        return False, None
    time.sleep(warmup)
    ok, frame = cap.read()
    cap.release()
    return ok, frame if ok else None

def test_picam(size=(640,480), warmup=2):
    picam = Picamera2()
    cfg = picam.create_preview_configuration(main={"size": size})
    picam.configure(cfg)
    picam.start()
    time.sleep(warmup)
    frame = picam.capture_array()
    picam.close()
    return frame

def main():
    print("=== 1) OpenCV USB 카메라 점검 ===")
    found = []
    for idx in range(0, 6):   # 보통 0~1이면 충분하지만 넉넉히
        ok, frame = test_opencv_cam(idx)
        if ok:
            path = SAVE_DIR / f"usb_cam{idx}.jpg"
            cv2.imwrite(str(path), frame)
            print(f"[OK] /dev/video{idx} (or index {idx}) 캡처 성공 -> {path}")
            found.append(idx)
        else:
            print(f"[--] index {idx} 열기 실패")

    if not found:
        print("USB 카메라 없음 (또는 권한/점유 문제)")
    else:
        print(f"USB 카메라 인덱스: {found}")

    print("\n=== 2) Picamera2 점검 ===")
    if PICAM_AVAILABLE:
        try:
            info = Picamera2.global_camera_info()
            print(f"Picamera2 감지 카메라 수: {len(info)}")
            for i, cam in enumerate(info):
                print(f"  [{i}] {cam.get('Model','?')}  {cam.get('CameraID','')}")
            # 실제 캡처
            frame = test_picam()
            path = SAVE_DIR / "picam_test.jpg"
            cv2.imwrite(str(path), frame)
            print(f"[OK] Picamera2 캡처 성공 -> {path}")
        except Exception as e:
            print("[!!] Picamera2 테스트 실패:", e)
    else:
        print("Picamera2 모듈이 설치/인식되지 않았습니다.")

    print("\n=== 완료 ===")

if __name__ == "__main__":
    main()
