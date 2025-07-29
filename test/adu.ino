#include <Servo.h>

// --- 핀 할당 --- //
const int IR1_PIN           = 2;  // IR센서 1
const int IR2_PIN           = 3;  // IR센서 2
const int motorSpeedPin     = 10; // 모터 속도(PWM) (ENA/ENB)
const int motorDirectionPin = 12; // 모터 방향제어(IN1/IN2)
const int SERVO_PIN         = 9;  // 서보 신호선

int value = 200;  // 모터 초기 속도

Servo servo;

void setup() {
  Serial.begin(9600);

  // IR센서 입력
  pinMode(IR1_PIN, INPUT_PULLUP);
  pinMode(IR2_PIN, INPUT_PULLUP);

  // 모터 출력
  pinMode(motorDirectionPin, OUTPUT);
  digitalWrite(motorDirectionPin, HIGH); // 방향(결선에 따라 정/역)
  analogWrite(motorSpeedPin, value);     // 초기 속도

  // 서보모터
  servo.attach(SERVO_PIN);
  servo.write(90);  // 기본 각도

  Serial.println("통합 제어 시작!");
}

void loop() {
  // --- IR센서 감지에 따른 모터/서보 동작 예시 --- //
  int ir1 = digitalRead(IR1_PIN);
  int ir2 = digitalRead(IR2_PIN);

  // 센서 1번 감지 → 서보 0도, 모터 최고속(255)
  if(ir1 == LOW) {
    servo.write(0);
    analogWrite(motorSpeedPin, 255);
    Serial.println("IR1 감지: 서보 0도, 모터 속도 255");
  }
  // 센서 2번 감지 → 서보 180도, 모터 중간속도(128)
  else if(ir2 == LOW) {
    servo.write(180);
    analogWrite(motorSpeedPin, 128);
    Serial.println("IR2 감지: 서보 180도, 모터 속도 128");
  }
  // 아무 센서도 감지 X → 서보 90도, 모터 멈춤
  else {
    servo.write(90);
    analogWrite(motorSpeedPin, 0);
    Serial.println("감지X: 서보 90도, 모터 정지");
  }

  // --- 시리얼로 모터 속도 수동조절도 가능 --- //
  if (Serial.available()) {
    value = Serial.parseInt();
    value = constrain(value, 0, 255);
    analogWrite(motorSpeedPin, value);
    Serial.print("시리얼 입력 → 모터 속도: ");
    Serial.println(value);
  }

  delay(100);
}
