import cv2

for idx in range(0, 4):
    cap = cv2.VideoCapture(idx)
    if cap.isOpened():
        print(f"Camera {idx}: opened.")
        ret, frame = cap.read()
        if ret:
            filename = f"identify_cam_{idx}.jpg"
            cv2.imwrite(filename, frame)
            print(f"  -> Frame saved as {filename}")
        else:
            print("  -> No frame!")
        cap.release()
    else:
        print(f"Camera {idx}: NOT opened.")
