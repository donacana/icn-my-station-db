# ICN Camera Sender (Android)

**ICN My Station — YOLO DEMO 실시간 영상 송출 Android 앱 (`v0.4`)**

실제 공항 CCTV를 대체하는 데모 환경에서, 스마트폰 후면 카메라 영상을 **640×360 (16:9) JPEG 프레임**으로 인메모리 압축하여 AWS EC2 FastAPI 백엔드(`/ws/yolo/camera`)로 실시간 스트리밍하는 Kotlin 기반 Android 앱입니다.

---

## 시스템 아키텍처 내 역할

```text
[Android 앱: ICN Camera Sender] ── /ws/yolo/camera ──▶ [EC2 FastAPI 백엔드] ── /ws/yolo/view ──▶ [웹 대시보드]
                                                             ▲   │
                                            /ws/yolo/worker  │   └── /ws/live ──▶ [구역 혼잡도·긴급 알림]
                                                             ▼
                                                    [YOLO GPU 워커]
```

---

## 주요 구현 기능

- **YOLO DEMO v0.4 바이너리 프레임 규격 준수**
  - `[4바이트 Big-Endian uint32 헤더 길이 N]` + `[N바이트 UTF-8 JSON 헤더]` + `[JPEG 바이트]`
  - 헤더 JSON: `{"cameraId": 1, "frameId": 1523, "capturedAt": 1762923785120, "width": 640, "height": 360}`
  - 연결마다 `frameId`를 `1`부터 1씩 증가시켜 전송
- **다중 카메라 선택 및 무중단 전환**
  - 설정 화면에서 카메라 프리셋 원터치 선택 지원:
    - 카메라 1: **T1 3번 출국장** (`cameraId = 1`)
    - 카메라 2: **T1 스카이허브 라운지(서편)** (`cameraId = 2`)
    - **직접 입력**: DB(`demo_yolo_cameras.camera_id`) 등록값 변경 시 임의 정수 ID 입력 가능
  - 송출 중 카메라를 변경하면 **카메라 프리뷰를 유지한 채** 기존 WebSocket 연결을 정상 종료하고 새 `cameraId`로 즉시 재연결
- **가로(Landscape) 전용 CCTV 촬영 및 16:9 비율 유지 센터 크롭**
  - `sensorLandscape` 고정으로 실제 CCTV와 동일한 16:9 가로 화각 촬영 지원
  - 센서 해상도/비율 차이에 의한 영상 늘어짐을 방지하기 위해 **16:9 Center-Crop 후 640×360 리사이징** 적용
- **Zero Disk I/O 인메모리 스트리밍 & 백프레셔 제어**
  - 단말기 저장소에 이미지 파일을 기록하지 않고 메모리 내에서 JPEG(품질 65%) 압축 후 즉시 전송
  - 기본 3 FPS 송출 및 서버 `hello` 메시지의 `maxFps` 이내로 전송 주기 동적 조절
  - 네트워크 적체 시 OkHttp 전송 큐 크기를 검사하여 오래된 프레임을 즉시 폐기(Drop)해 실시간성 유지
- **자동 재연결 및 계약 종료 코드 대응**
  - 비정상 단절 시 `1초 → 2초 → 4초(최대 4초)` 지수 백오프 재연결
  - 계약 종료 코드별 안내 및 불필요한 재연결 루프 방지: `4401`(토큰 오류), `4404`(미등록 카메라 ID), `4409`(동일 카메라 ID 중복 연결 대체)

---

## YOLO DEMO v0.4 계약 요약

| 항목 | 규격 | 앱 구현 |
| :--- | :--- | :--- |
| **WebSocket 경로** | `ws(s)://<host>/ws/yolo/camera?cameraId=1&token=<token>` | `ProtocolConfig.kt` |
| **카메라 식별자** | 정수 `cameraId` (`1`, `2` 또는 사용자 입력) | `AppPreferences.kt`, `MainActivity.kt` |
| **인증 방식** | 쿼리 파라미터 `token` (`YOLO_CAMERA_TOKEN`) | 설정 패널 입력, `SharedPreferences` 저장 (로그 미출력) |
| **바이너리 패킷** | `[uint32 N (Big-Endian)]` + `[UTF-8 JSON]` + `[JPEG]` | `YoloDemoV4PayloadFormatter` |
| **해상도 / 압축** | `640×360` (16:9 Center-Crop), JPEG 품질 `65%`, 기본 `3 FPS` | `CameraManager.kt` |
| **핸드셰이크** | 서버 `{"type": "hello", "cameraId": 1, "maxFps": 10}` 수신 | `WebSocketManager.kt`, `CameraManager.kt` |

---

## 프로젝트 구조

```text
mobile/android-camera/
├── app/
│   ├── build.gradle.kts                          # AndroidX, CameraX 1.3.4, OkHttp 4.12.0 의존성
│   └── src/main/
│       ├── AndroidManifest.xml                   # CAMERA/INTERNET 권한, sensorLandscape, 네트워크 설정
│       ├── java/com/icn/camerasender/
│       │   ├── camera/CameraManager.kt           # CameraX 프리뷰/분석, 16:9 센터 크롭, 640x360 JPEG 65% 인메모리 압축
│       │   ├── config/AppPreferences.kt          # 서버 URL, 정수 cameraId, 인증 토큰 SharedPreferences 관리
│       │   ├── model/
│       │   │   ├── ConnectionState.kt            # WebSocket 연결 상태 모델
│       │   │   └── StreamStatistics.kt           # 실시간 FPS, 전송/폐기 프레임 수 집계
│       │   ├── network/WebSocketManager.kt       # OkHttp WebSocket, 1s→2s→4s 재연결, 4401/4404/4409 처리, 큐 드롭
│       │   ├── protocol/
│       │   │   ├── ProtocolConfig.kt             # v0.4 URL 빌더, hello 파싱, 종료 코드 매핑
│       │   │   └── FramePayloadFormatter.kt      # v0.4 바이너리 패킷 포맷터
│       │   └── ui/MainActivity.kt                # 카메라 1/2/직접입력 전환 UI, 무중단 재연결, 실시간 지표 표시
│       └── res/
│           ├── layout/activity_main.xml          # 가로 모드 최적화 프리뷰·상태바·스크롤 설정 패널
│           ├── values/                           # colors.xml, strings.xml, themes.xml
│           └── xml/network_security_config.xml   # 개발/DEMO 환경 평문(ws://) 통신 허용
├── server_example/
│   ├── fastapi_server.py                         # 로컬 테스트용 FastAPI WebSocket 수신 모의 서버
│   └── requirements.txt
└── README.md
```

---

## 빌드 및 실행 방법

### 1. Android Studio 빌드
- **Requirements**: Android Studio, JDK 17+, Android SDK 34 (`minSdk 24`, `targetSdk 34`)
- 프로젝트를 Android Studio로 연 뒤 실기기(USB 디버깅)에서 **Run (▶)** 실행
- CLI 빌드 예시:
  ```bash
  ./gradlew assembleDebug
  ```

### 2. 앱 초기 설정
1. 앱 실행 후 우측 상단 **⚙️ 설정** 버튼을 누릅니다.
2. 송출할 카메라(`카메라 1`, `카메라 2`, 또는 `직접 입력`)를 선택합니다.
3. **WebSocket 서버 주소** (`ws://<SERVER_HOST>/ws/yolo/camera` 또는 `wss://...`)와 백엔드 **인증 토큰(`YOLO_CAMERA_TOKEN`)**을 입력하고 **[설정 저장 및 적용]**을 누릅니다.
4. 하단 **[송출 시작]** 버튼을 눌러 실시간 영상 송출을 시작합니다.

### 3. 로컬 모의 서버 테스트 (`server_example/`)
백엔드 없이 로컬 PC에서 바이너리 프레임 수신 및 파싱을 검증할 수 있습니다:

```bash
cd server_example
pip install -r requirements.txt
python fastapi_server.py
```


## 버전 및 데모 범위

- 앱 버전은 1.0.0이며, v0.4는 [YOLO DEMO 통신 계약](../../docs/yolo-demo-contract.md)의 버전입니다.
- [YOLO 워커](../../workers/yolo/)는 별도 실행합니다. 앱은 영상 송출만 담당합니다.
- 서버 예제는 v0.3 기반 로컬 수신 예제이며, 전체 백엔드 계약 구현은 아닙니다. 테스트 토큰은 demo-camera-token이고 운영 인증정보가 아닙니다.
- 서버 예제 접속 주소는 ws://<PC_HOST>:8000/ws/yolo/camera입니다.
- 토큰은 단말의 SharedPreferences에 평문 저장됩니다. ws:// 연결도 평문이므로 실제 인증정보를 사용하는 환경에서는 wss://를 사용하세요.
- 현재 release 빌드는 debug 서명을 사용합니다. 스토어 배포용 서명 설정은 별도로 필요합니다.
- Windows CLI 빌드: 프로젝트 폴더에서 .\gradlew.bat assembleDebug 실행.
