import cv2
import serial
import threading
import queue
import time
import requests
from loguru import logger

# ───────────── 사용자 환경 맞게 설정 ─────────────
SENS_PORT  = '/dev/ttyACM2'  # 아두이노 (센서+모터+서보)
BAUD = 115200

CAM_MAIN_IDX  = 1  # 일반카메라 (확인 필요!)
CAM_MICRO_IDX = 0  # 현미경 (확인 필요!)

AI_DEFECT_URL = "http://34.64.178.127:8000/upload"
AI_GRADE_URL  = "http://34.64.178.127:8000/upload"

# ───────────── 장치 연결/체크 ─────────────
def open_camera(idx):
    logger.info(f"[open_camera] 카메라 {idx} 열기 시도")
    cap = cv2.VideoCapture(idx)
    if not cap.isOpened():
        logger.error(f"[open_camera] 카메라 {idx} 열기 실패!")
        return None
    logger.info(f"[open_camera] 카메라 {idx} 사용 준비 완료")
    return cap

logger.info("[시작] 카메라 초기화 시도")
cap_main  = open_camera(CAM_MAIN_IDX)
cap_micro = open_camera(CAM_MICRO_IDX)
if cap_main is None or cap_micro is None:
    logger.error("[FATAL] 카메라 연결 문제로 종료")
    exit(1)

logger.info("[시작] 아두이노 시리얼 연결 시도")
try:
    sens = serial.Serial(SENS_PORT, BAUD, timeout=1)
    logger.info(f"[시리얼] {SENS_PORT} 아두이노 연결 OK")
except Exception as e:
    logger.error(f"[FATAL] 시리얼 포트 연결 실패: {e}")
    exit(1)

events = queue.Queue()
def listen_sens():
    logger.info("[listen_sens] 센서 이벤트 리스너 시작")
    while True:
        try:
            line = sens.readline().decode(errors="ignore").strip()
            logger.debug(f"[listen_sens] 수신 라인: '{line}'")
            if line:
                logger.info(f"[listen_sens] [센서] '{line}' 이벤트 큐에 추가")
                events.put(line)
        except Exception as e:
            logger.error(f"[listen_sens] 센서 리드 오류: {e}")
            time.sleep(0.5)
threading.Thread(target=listen_sens, daemon=True).start()

# ───────────── AI 서버 연동 함수 ─────────────
def predict_defect(frame) -> bool:
    logger.info("[predict_defect] 결함 판정 이미지 인코딩 시도")
    ok, img_encoded = cv2.imencode('.jpg', frame)
    if not ok:
        logger.error("[predict_defect] 이미지 인코딩 실패")
        raise RuntimeError("이미지 인코딩 실패")
    files = {'file': ('image.jpg', img_encoded.tobytes(), 'image/jpeg')}
    try:
        logger.info(f"[predict_defect] AI 서버 요청 시도: {AI_DEFECT_URL}")
        response = requests.post(AI_DEFECT_URL, files=files, timeout=5)
        logger.info("[predict_defect] AI 서버 응답 수신")
        response.raise_for_status()
        result = response.json()
        logger.info(f"[predict_defect] AI 결과: {result}")
        return result.get("label", "").upper() == "DEFECT"
    except Exception as e:
        logger.error(f"[predict_defect] 서버 통신 실패: {e}")
        raise RuntimeError(f"[predict_defect] 서버 통신 실패: {e}")

def classify_grade(frame) -> str:
    logger.info("[classify_grade] 등급 판정 이미지 인코딩 시도")
    ok, img_encoded = cv2.imencode('.jpg', frame)
    if not ok:
        logger.error("[classify_grade] 이미지 인코딩 실패")
        raise RuntimeError("이미지 인코딩 실패")
    files = {'file': ('image.jpg', img_encoded.tobytes(), 'image/jpeg')}
    try:
        logger.info(f"[classify_grade] AI 서버 요청 시도: {AI_GRADE_URL}")
        response = requests.post(AI_GRADE_URL, files=files, timeout=5)
        logger.info("[classify_grade] AI 서버 응답 수신")
        response.raise_for_status()
        result = response.json()
        logger.info(f"[classify_grade] AI 결과: {result}")
        return result.get("grade", "").upper()
    except Exception as e:
        logger.error(f"[classify_grade] 서버 통신 실패: {e}")
        raise RuntimeError(f"[classify_grade] 서버 통신 실패: {e}")

# ───────────── 아두이노 명령 송신 ─────────────
def motor_cmd(cmd: str):
    try:
        logger.info(f"[motor_cmd] '{cmd}' 명령 송신 시도")
        sens.write(f'{cmd}\n'.encode())
        logger.info(f"[motor_cmd] '{cmd}' 명령 송신 성공")
    except Exception as e:
        logger.error(f"[motor_cmd] 송신 오류: {e}")

motor_cmd('MOTOR START')
logger.info("[메인] 시스템 준비. 이벤트 대기 중...")

# ───────────── 메인 루프 ─────────────
try:
    while True:
        logger.info("[main] 이벤트 대기 중...")
        evt = events.get()
        logger.info(f"[main] 이벤트 수신: {evt}")

        if evt == 'TRIG1':
            logger.info("[main] TRIG1 분기 진입")
            motor_cmd('MOTOR STOP')
            logger.info("[main] 메인 카메라 캡처 시도")
            ok, frame = cap_main.read()
            if not ok:
                logger.error("[main] 메인 카메라 캡처 실패")
                motor_cmd('MOTOR START')
                continue
            logger.info("[main] 메인 카메라 캡처 성공, 결함 판정 시도")
            try:
                defect = predict_defect(frame)
            except Exception as e:
                logger.error(f"[main] 불량 판독 오류: {e}")
                motor_cmd('MOTOR START')
                continue

            logger.info(f"[main] 판정 결과: defect={defect}")
            if defect:
                logger.info("[main] 결함 감지, SERVO 150 명령 송신")
                motor_cmd('SERVO 150')
                logger.info("[main] 불량 → C구역(서보 150)")
            else:
                logger.info("[main] 정상 → 2단계(현미경)로 이동")
            motor_cmd('MOTOR START')

        elif evt == 'TRIG2':
            logger.info("[main] TRIG2 분기 진입")
            motor_cmd('MOTOR STOP')
            logger.info("[main] 현미경 카메라 캡처 시도")
            ok, frame = cap_micro.read()
            if not ok:
                logger.error("[main] 현미경 캡처 실패")
                motor_cmd('MOTOR START')
                continue
            logger.info("[main] 현미경 카메라 캡처 성공, 등급 판정 시도")
            try:
                grade = classify_grade(frame)
            except Exception as e:
                logger.error(f"[main] 등급 판정 오류: {e}")
                motor_cmd('MOTOR START')
                continue

            logger.info(f"[main] 판정 결과: grade={grade}")
            angle = 30 if grade == 'A' else 90
            logger.info(f"[main] SERVO {angle} 명령 송신")
            motor_cmd(f'SERVO {angle}')
            logger.info(f"[main] 등급 {grade} → 서보 {angle}")
            motor_cmd('MOTOR START')

        else:
            logger.warning(f"[main] 알 수 없는 이벤트: '{evt}'")

except KeyboardInterrupt:
    logger.info("[main] 수동 종료 요청, 프로그램을 종료합니다.")
finally:
    logger.info("[main] 리소스 정리 시작")
    if cap_main: cap_main.release()
    if cap_micro: cap_micro.release()
    if sens and sens.is_open: sens.close()
    logger.info("[main] 리소스 정리 및 종료 완료.")
