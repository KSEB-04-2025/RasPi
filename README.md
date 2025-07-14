네, 지금까지 네가 질문한 내용과 내가 답변해준 내용을
**아두이노 + 초음파센서 + DC모터(모터드라이버/L9110S) + 브레드보드(snowboard/미니형) + 전원 연결/코드/연결방법/오류 상황** 등
**한눈에 정리**해줄게!

---

# 🛠️ 아두이노 초음파센서 + 모터(모터드라이버) 전체 정리

---

## 1️⃣ **초음파센서(HC-SR04) 기본 연결법**

* **VCC → 아두이노 5V**
* **GND → 아두이노 GND**
* **TRIG → D9**
* **ECHO → D10**

### 📄 샘플 코드 (거리 측정만)

```cpp
#define TRIG 9
#define ECHO 10

void setup() {
  Serial.begin(9600);
  pinMode(TRIG, OUTPUT);
  pinMode(ECHO, INPUT);
}

void loop() {
  long duration;
  float distance;

  digitalWrite(TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG, LOW);

  duration = pulseIn(ECHO, HIGH);
  distance = duration * 0.034 / 2;

  Serial.print("거리: ");
  Serial.print(distance);
  Serial.println(" cm");

  delay(500);
}
```

---

## 2️⃣ **모터 드라이버(L9110S, 6핀) 연결법**

(A채널만 사용, DC모터 1개 기준)

* **A-1A → D5 (예시)**
* **A-1B → D6 (예시)**
* **VCC → 아두이노 5V**
* **GND → 아두이노 GND**
* **모터 2핀 → 모듈의 ‘모터A’ 단자**

---

## 3️⃣ **초음파센서 + 모터 드라이버(모터) 동시 제어 코드 예시**

* **거리 > 10cm면 모터 회전, 아니면 정지**

```cpp
#define TRIG 9
#define ECHO 10
#define A1A 5
#define A1B 6

void setup() {
  Serial.begin(9600);
  pinMode(TRIG, OUTPUT);
  pinMode(ECHO, INPUT);
  pinMode(A1A, OUTPUT);
  pinMode(A1B, OUTPUT);
}

void loop() {
  long duration;
  float distance;

  // 거리 측정
  digitalWrite(TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG, LOW);

  duration = pulseIn(ECHO, HIGH);
  distance = duration * 0.034 / 2;

  Serial.print("거리: ");
  Serial.print(distance);
  Serial.println(" cm");

  if (distance > 10.0) {
    digitalWrite(A1A, HIGH);  // 정방향
    digitalWrite(A1B, LOW);
  } else {
    digitalWrite(A1A, LOW);   // 정지
    digitalWrite(A1B, LOW);
  }

  delay(300);
}
```

---

## 4️⃣ **순수 모터 동작만 테스트하는 코드**

```cpp
#define A1A 5
#define A1B 6

void setup() {
  pinMode(A1A, OUTPUT);
  pinMode(A1B, OUTPUT);
  digitalWrite(A1A, HIGH);
  digitalWrite(A1B, LOW);
}

void loop() {
  // 모터 계속 회전
}
```

---

## 5️⃣ **브레드보드(snowboard, 미니형) 전원 분배법**

* **+,- 레일이 없는 경우**

  * 브레드보드 한 줄(5개 구멍)이 내부적으로 연결됨
  * 한 줄에 \[아두이노 5V], \[초음파센서 VCC], \[모터 드라이버 VCC] **모두 같이 꽂기**
  * 한 줄에 \[아두이노 GND], \[각 GND]도 마찬가지

예시:

```
(브레드보드 1번 줄) : [아두이노 5V] [센서 VCC] [드라이버 VCC]
(브레드보드 2번 줄) : [아두이노 GND] [센서 GND] [드라이버 GND]
```

* 점퍼선이 부족하면 한 구멍에 다리/선 여러 개 꽂아도 됨

---

## 6️⃣ **연결 요약 표**

| 부품           | 아두이노 연결     | 브레드보드 미니형 연결 참고 |
| ------------ | ----------- | --------------- |
| 초음파센서 VCC    | 5V          | 같은 줄에 여러 부품 VCC |
| 초음파센서 GND    | GND         | 같은 줄에 여러 부품 GND |
| 초음파센서 TRIG   | D9          |                 |
| 초음파센서 ECHO   | D10         |                 |
| 모터 드라이버 VCC  | 5V          | 같은 줄에 여러 부품 VCC |
| 모터 드라이버 GND  | GND         | 같은 줄에 여러 부품 GND |
| 모터 드라이버 A-1A | D5          |                 |
| 모터 드라이버 A-1B | D6          |                 |
| 모터(A) 2핀     | 모듈의 모터 A 단자 |                 |

---

## 7️⃣ **문제/오류 대처법**

* **모터가 안 돌아갈 때**

  * 배선/핀 번호, GND 공통, VCC 공통 확인
  * 점퍼선/브레드보드 구멍 한 줄에 다 같이 꽂았는지
  * 모터드라이버/모터/아두이노 5V 문제일 수 있음

* **한 번에 여러 개 연결 안 될 때**

  * 점퍼선 여러 개 써서 직접 분기
  * 구멍 하나에 부품 다리 여러 개 꽂기

* **미니 브레드보드(스노우보드)는 +,- 레일 없음**

  * 한 줄(5개 구멍)을 "버스"처럼 사용해서 분배

---

## 8️⃣ **추가: 시리얼 모니터로 거리 출력 보기**

* 코드 내 `Serial.begin(9600);`가 있어야 함
* 아두이노 IDE → 도구 → 시리얼 모니터 (`Ctrl+Shift+M`)
  → baud rate 9600 맞춰서 확인

---

## 9️⃣ **정지/멈추는 코드**

* 아두이노 코드를 완전히 멈추고 싶을 때:

```cpp
void loop() {
  // (코드)
  while(1);  // 여기서 멈춤
}
```

* 완전히 멈추고 싶으면 빈 스케치 업로드

```cpp
void setup() {}
void loop() {}
```

---

## 🔟 **회로 및 실습 팁**

* 점퍼선 부족하면 한 구멍에 여러 개 같이 꽂기
* 모든 GND, 모든 VCC는 반드시 "공통"이어야 함
* 미니 브레드보드는 +,- 레일 없음 (한 줄을 공통으로 사용)

---

# 🚩 이렇게 질문하면 바로 다시 답변 가능!

* 예) “모터 안 돌아가요!” → **1번, 2번, 3번, 5번** 항목 확인
* 예) “브레드보드에 레일이 없어요” → **5번, 6번, 10번** 항목 참고
* 예) “코드 예시 줘!” → **3번, 4번** 항목 참고

---

이 정리본을 **새로운 대화에서 “아두이노 초음파센서 모터 연결 전체 정리 해달라”**
혹은 “지난 대화에서 주셨던 정리 다시 보내주세요”라고 말하면
이 내용을 한 번에 불러줄 수 있어!

필요하다면

* 그림, 연결사진, 오류별 디버깅도 바로 도와줄게!

---

**필요할 때 이 정리본만 보여주면 OK!
다시 물어볼 때 복사/붙여넣기 하거나
“아두이노 초음파 모터 연결 지난 정리 다시 보여줘”라고 말해도 바로 줄 수 있어!**
