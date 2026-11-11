> 2026-11-10 로컬 Worker 개발 보고서 사본입니다. 이번 커밋에는 문서만 포함되며, 본문의 실행 스크립트·코드·모델·원본 측정 파일은 Windows Worker 프로젝트에 있습니다.

# 실제 EC2 연동 준비 보고서

## 현재 상태

Windows Worker 구현 및 로컬 Mock 통신은 검증했다. **실제 EC2에 접속하지 않았으며 실제 통신 계약 어댑터는 미완료**다. Android/React/EC2/RDS/Nginx는 수정하지 않았다.

현재 주소는 `ws://127.0.0.1:8765/ws/yolo/worker`다. 외부 주소와 MOCK_MODE=false는 실행 전에 거부한다. 실제 주소와 인증 토큰만 입력하는 것으로 미확정 계약을 해결할 수는 없다.

## 백엔드 담당자에게 받을 정보

| 항목 | 확인할 내용 |
|---|---|
| Worker 주소 | 승인된 테스트/운영 환경, wss URL, /ws/yolo/worker 경로 |
| 인증 | 헤더/등록 메시지 방식, 토큰 발급·만료·재발급, 401/403 및 close code |
| 등록 | workerId, cameraId, capabilities, 등록 ACK 구조 |
| JPEG 바이너리 | ICN1 사용 여부, 버전, 엔디언, 헤더 길이, 최대 크기, 단위 |
| frame metadata | cameraId, frameId, capturedAt, camera session, 해상도, 순서 보장 |
| 결과 JSON | 필수 필드/타입, bbox 형식, class ID 의미, track ID 범위, 추론 장치 |
| 상태 | STALE/OFFLINE, 끊김/재개, 세션 변경 메시지, 미검출과 데이터 없음 구별 |
| 이벤트 | help_candidate 승인 여부, confirmed=false, eventId 중복 제거, timestamp 형식 |
| 연결 유지 | Ping/Pong 및 앱 heartbeat 구별, timeout, 재연결 시 재등록 |
| 폐기 정책 | 오래된 프레임/결과, 시계 오차, 최대 FPS, 역전·중복 frameId |
| 오류 | 오류 JSON/close code, 재시도 가능 여부, 모델 실패 통지 |

## 현재 Mock v1 바이너리 계약 — 최종 EC2 규격 아님

모든 정수는 **unsigned, big-endian/network order**, 문자열은 **UTF-8**다.

| 필드 | 바이트 | 의미 |
|---|---:|---|
| magic | 4 | ASCII ICN1 |
| version | 2 | 1 |
| frameId | 8 | 카메라 세션 내 단조 증가 uint64 |
| capturedAt | 8 | Unix epoch milliseconds |
| cameraIdLength | 2 | UTF-8 바이트 수, 1~128 |
| cameraId | 가변 | printable 문자열 |
| jpegSize | 4 | JPEG 바이트 수, 1~8,388,608 |
| JPEG | 가변 | 실제 JPEG 바이트 |

고정 앞 헤더는 24바이트다. 전체 최대 길이는 8,388,764바이트다. 남는 바이트·잘린 길이·잘못된 버전/UTF-8은 거부한다. 디코딩에서는 JPEG 시작/종료, 크기, 형식, 최대 픽셀 수를 추가 검사한다.

세션 ID는 이 바이너리에 들어 있지 않다. Worker 연결마다 생성하는 UUID와 카메라 generation으로 범위를 구분한다. 같은 WebSocket의 카메라 세션 변경은 아래 control을 먼저 보내야 한다. 실제 계약이 per-frame sessionId를 요구하면 바이너리 어댑터를 변경해야 한다.

## 등록·컨트롤·응답

인증은 설정된 경우 HTTP `Authorization: Bearer <WS_TOKEN>` 헤더를 사용한다. 로컬 Mock도 토큰이 설정되어 있으면 검사한다.

Worker 등록:

```json
{"type":"register","protocol":"mock-v1","cameraId":"DEMO_T1_3","sessionId":"connection-uuid"}
```

서버 ACK:

```json
{"type":"registered","protocol":"mock-v1"}
```

카메라 제어:

```json
{"type":"camera_session","cameraId":"DEMO_T1_3","sessionId":"camera-session-2"}
{"type":"camera_offline","cameraId":"DEMO_T1_3"}
```

세션이 바뀌면 frameId와 캡처 시각의 순서 기준을 초기화하고, 기존 처리 중 결과를 폐기한다. 같은 카메라 세션의 timestampMs는 증가해야 한다. 카메라당 기본 3 FPS이므로 같은 밀리초 프레임은 허용하지 않는다.

탐지 응답에는 type, cameraId, frameId, sessionId, cameraGeneration, timestampMs, status=LIVE, personCount, countSource=person, modelVersion, inferenceBackend, inferenceMs, detections, events가 포함된다. detections의 bbox는 원본 JPEG 기준 **[x1,y1,x2,y2] / 0~1 정규화**다. trackId는 초기 프레임에 null일 수 있다. ID는 person 신원이 아니며 프로세스 재시작을 넘어서 비교하지 않는다.

데이터 상태 응답:

```json
{"type":"camera_status","cameraId":"DEMO_T1_3","status":"OFFLINE","personCount":null}
```

STALE도 동일 형식이다. 마지막 프레임 이후 5초에 STALE, 10초에 OFFLINE을 판단한다. 데이터 없음은 0명으로 단정하지 않는다. 시간 검사에는 로컬 시계와 캡처 시각 차이가 영향을 주므로 실제 계약에서 시계 동기화/허용 오차를 정해야 한다.

제스처 이벤트는 help_candidate이며 confirmed=false다. 현재 COCO 모델은 events=[]다. 후보의 모델 검증이 끝나지 않았으므로 대시보드 긴급 모달로 자동 확정하지 않는다.

## 실제 계약 적용 범위

1. `app/protocol.py`: 등록/ACK/바이너리/control/결과/status 어댑터 추가
2. `app/config.py`: 실제 adapter 선택 및 URL·보안 정책 검증 구현
3. `app/ws_client.py`: 계약이 지정한 인증과 연결 수명 처리 반영
4. 계약 fixture로 protocol/WebSocket 테스트 추가
5. 승인된 테스트 환경에서 사용자가 연결 수행

탐지 엔진, ByteTrack, 인원 수, 최신 프레임 버퍼는 공통 인터페이스를 유지한다. 다중 카메라를 한 연결로 받으려면 현재 1카메라 허용 정책과 스케줄링을 별도로 확장한다.

현재 연결 유지: WS Ping 20초 / Pong timeout 20초 / open timeout 10초 / close timeout 3초. 재접속은 0.5초부터 최대 30초 기준 지수 백오프와 ±20% jitter를 사용한다. 인증 거부는 재시도하지 않는다. 대기 프레임은 카메라당 1개이며 순서 역전·중복·시효 초과는 폐기한다.

## 남은 검증

- best.onnx/best.pt/data.yaml 실제 클래스와 export 형식
- 최종 도움 요청 학습 모델 정확도, 동일 손 연결, 오탐률
- 민규의 최종 WebSocket 계약과 실제 인증
- 실제 휴대폰 → EC2 → Worker → 대시보드 통합
- 장시간 연결, 다중 카메라, 실제 혼잡 장면의 인원 정확도
