GET
	http://34.64.123.85:8000/upload/
Status
404
Not Found
VersionHTTP/1.1
Transferred154 B (22 B size)
Request PriorityHighest
DNS ResolutionSystem

	
content-length
	22
content-type
	application/json
date
	Fri, 11 Jul 2025 02:02:43 GMT
server
	uvicorn
	
Accept
	text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8
Accept-Encoding
	gzip, deflate
Accept-Language
	en-US,en;q=0.5
Cache-Control
	no-cache
Connection
	keep-alive
Host
	34.64.123.85:8000
Pragma
	no-cache
Priority
	u=0, i
Upgrade-Insecure-Requests
	1
User-Agent
	Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0


**root01@raspberrypi:~/Desktop/Project $ python a.py
✅ 아두이노 연결 성공. 신호 대기 중...
📥 수신된 신호: CAPTURE
📸 성공: 이미지 저장 완료 → /home/root01/Desktop/captured_images/capture_20250710_155259.jpg
❌ 서버 전송 실패: 404 Client Error: Not Found for url: http://34.64.123.85:8000/upload/
📥 수신된 신호: CAPTURE
📸 성공: 이미지 저장 완료 → /home/root01/Desktop/captured_images/capture_20250710_155304.jpg
❌ 서버 전송 실패: 404 Client Error: Not Found for url: http://34.64.123.85:8000/upload/
^C🔌 종료**
