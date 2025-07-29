import serial

for port in ["/dev/ttyACM0", "/dev/ttyACM1"]:
    try:
        ser = serial.Serial(port, 115200, timeout=2)
        ser.write(b'CHECK\n')   # 본인 펌웨어에서 "CHECK" 명령에 대한 응답 처리
        resp = ser.readline().decode(errors='ignore').strip()
        print(f"{port} → '{resp}'")
        ser.close()
    except Exception as e:
        print(f"{port} → 에러: {e}")
