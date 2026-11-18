# 돌아온 후 가장 먼저 확인할 내용

2026-11-11: 사용자 제공 **YOLO DEMO 계약 v0.3**와 배포 커밋 `8f08a05`를 대조했다. 외부 EC2 Worker 모드를 구현했고 Android·백엔드·EC2·방화벽은 수정하지 않았다.

## 0. 실제 EC2 연결

배포 담당자가 제공한 공개 주소의 `/api/v1/yolo/cameras`와 `/ws/yolo/worker`를 사용한다. 실제 주소와 토큰은 `.env.ec2`에만 두며 저장소에 커밋하지 않는다. EC2 내부 애플리케이션 포트로 직접 접속하지 않는다.

실제 `YOLO_WORKER_TOKEN` 로딩과 EC2 인증은 성공했다. 다음 명령은 재실행용이다.

```powershell
Set-Location '<repository>\workers\yolo'
.\.venv\Scripts\python.exe -m tools.check_ec2_status
.\run-ec2-worker.ps1
```

`.env.ec2`는 Git 제외 대상이다. 현재 설정은 최종 `models/best.onnx`, ONNX CPU, cameraId 1, workerId `suam-school-pc`, modelVersion `icn-v1-yolo11n-finger-gun`, classes `["person", "finger_gun"]`, gesture 비활성화다. demo fallback도 금지했다. Ctrl+C로 끝내면 최종 수신·처리·전송·FPS·평균 지연·재연결 횟수가 콘솔에 집계된다.

2026-11-11 실제 Worker와 Android camera가 모두 ONLINE으로 전환됐고, 실제 JPEG 수신·추론·결과 송신을 확인했다. 당시 장면의 탐지는 0건이었으며 가짜 결과는 보내지 않았다. 최신 상세 결과는 `final_model_report.md`에 있다.

## 1. 휴대폰 없이 재현

```powershell
Set-Location '<repository>\workers\yolo'
.\demo-relay.ps1
.\test.ps1 -Real
```

`demo-relay.ps1`은 별도 FastAPI 중계/Worker 프로세스를 띄워 ICN1·Raw JPEG·v0.3 프레임을 각각 6장 전송한다. 실제 ONNX 사람 검출, ByteTrack, JSON 응답, 중계 재시작 후 Worker 재연결을 검사하고 자신이 시작한 프로세스를 종료한다. 보통 25~35초 걸린다. 결과는 `reports/local_relay_demo.json`이다. 공개 NASA 테스트 이미지만 사용하며 카메라 장치를 켜지 않는다.

현재 의존성은 설치되어 있다. 새 환경에서는 `./setup.ps1 -Relay`를 사용한다. 스크립트 실행 정책 때문에 막히면 정책 변경 대신 `./.venv/Scripts/python.exe -m tools.relay_demo`로 실행한다.

## 2. 실제 휴대폰 연결 — Android v0.3 대응 후 실행

**카메라 번호 1은 로컬 테스트 값이다.** 박수암이 DB 등록 후 공유하는 실제 번호로 두 실행 명령의 `-CameraId`와 앱 설정을 함께 바꾼다.

과거에 확인한 Android 소스는 JSON cameraId를 문자열로 전송했지만, 현재 실제 배포 앱의 프레임은 v0.3 중계를 통과해 Worker에 도착했다. 이 작업에서는 Android 읽기 전용 지시를 유지하여 수정/빌드하지 않았다. 아래 설정은 로컬 재현용이다.

PC와 휴대폰을 같은 신뢰할 수 있는 Wi-Fi/LAN에 연결한다. PowerShell 두 개에서 각각 실행한다.

```powershell
# 창 1: 휴대폰이 접근할 수 있게 명시적으로 LAN 바인딩
Set-Location '<repository>\workers\yolo'
.\run-relay.ps1 -BindAddress 0.0.0.0 -Port 8000 -CameraId 1
```

```powershell
# 창 2: Worker는 같은 PC의 localhost 중계에만 접속
Set-Location '<repository>\workers\yolo'
.\run-relay-worker.ps1 -Port 8000 -CameraId 1
```

`Get-NetIPConfiguration`에서 실제 연결된 어댑터의 IPv4를 확인한다. 휴대폰 앱 UI에 다음 값을 저장한다.

- Camera ID: `1`
- 서버 URL: `ws://<PC의 IPv4>:8000/ws/yolo/camera`
- 카메라 토큰 입력란: `local-camera-demo`
- v0.3 대응 APK에서 cameraId/token 쿼리를 앱이 붙이는 UI인 경우다. URL에 쿼리를 중복 입력하지 않는다.
- 휴대폰에 설치된 APK가 이전 HEADER/RAW UI라면 전체 URL `ws://<PC의 IPv4>:8000/ws/yolo/camera?cameraId=1&token=local-camera-demo`와 HEADER 모드를 사용한다. 로컬 어댑터는 구버전도 지원한다.
- 권장: 640×360, 3 FPS, JPEG 품질 65

URL의 `<PC의 IPv4>`를 실제 숫자 주소로 바꾼다. 휴대폰에서 `localhost`나 `0.0.0.0`을 접속 주소로 쓰지 않는다. 앱은 경로를 자동으로 붙이지 않으므로 `/ws/yolo/camera`까지 입력한다.

기본 토큰 `local-camera-demo` / `local-worker-demo`는 공개된 **로컬 테스트 전용 값**이다. 다른 값을 쓰려면 중계 창에 `YOLO_CAMERA_TOKEN`, `YOLO_WORKER_TOKEN` 환경변수를 설정하고 Worker 창에는 동일한 `YOLO_WORKER_TOKEN`, 현재 앱의 토큰 입력란에는 카메라 토큰을 설정한다. 실제 운영 비밀을 이 데모에 복사하지 않는다. `ws://`는 암호화되지 않는다.

PC에서 결과 확인:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/status
Invoke-RestMethod http://127.0.0.1:8000/result | ConvertTo-Json -Depth 8
```

`LIVE`, `personCount`, `trackId`를 확인한다. 초기 프레임의 ID는 null일 수 있다. 영상이 끊기면 `OFFLINE/STALE`과 null 인원을 반환하며 0명으로 오해하지 않는다. 결과는 메모리에만 보관하고 Android로 보내 로그에 남기지 않는다. 이 두 조회 API는 PC loopback에서만 접근할 수 있다.

종료는 각 창에서 Ctrl+C다. 연결되지 않으면 PC IP, 같은 네트워크, AP 격리, 포트 8000 점유 여부를 확인한다. 방화벽 전체 해제·자동 예외 추가는 하지 않는다. 네트워크 정책 때문에 차단되면 관리자에게 필요한 포트의 제한된 허용 여부를 확인한다.

## 3. 실제 모델과 EC2로 넘어가기 전

1. 학습 담당자에게 동일 YOLO11n 학습 결과의 `best.onnx`, `best.pt`, `data.yaml`을 받는다.
2. 정확한 클래스 이름과 입력/출력 shape를 확인한다. v0.3 손동작 이름은 정확히 `help_gesture`다. `help_open/help_fist`를 임의로 대응시키지 않는다.
3. `models/`에 배치하고 `.env`의 `CLASS_MAP_PATH=models/data.yaml` 등 모델 설정을 검토한 다음 `tools.inspect_model`과 실제 입력으로 검증한다. `demo-relay.ps1`은 재현성을 위해 공식 `yolo11n.onnx`를 명시적으로 사용한다. 학습 모델은 `run-relay-worker.ps1`로 따로 시험한다.
4. 백엔드 담당자와 `integration_report.md`의 카메라 세션 확장, head 단독 인원 정책, 오류 응답 상관관계, 시계 오차를 확인한다.
5. 실제 서버 주소와 v0.3 어댑터는 적용됐다. 실제 토큰을 `.env.ec2`에 넣고 위 운영 스크립트로 통합 테스트한다.
6. 휴대폰 → EC2 → Worker → 기존 대시보드에서 영상·인원·알림을 검증한다. `/ws/yolo/view`, `/ws/live`, REST, DB 구현은 기존 백엔드/프론트 담당 범위다.

최종 best.onnx는 `person`, `finger_gun`만 반환한다. `head/help_gesture`를 임의 생성하지 않고 긴급 이벤트도 비활성화했다. 실제 휴대폰 송출과 EC2 왕복은 검증했지만, 당시 장면에서 person/finger_gun 양성은 없었다. 로컬 사람 탐지는 성공했고 실제 finger_gun 양성 정확도는 아직 미검증이다.

## 4. 보고서 게시 이력

기존 2026-11-10 보고서 5개는 GitHub `feature/jenkins-setup`의 `docs/yolo-worker-reports/2026-11-10/`에 게시되어 있다. 커밋: `d2de05fd4d1767206957f2c704233fd69ea54961`. main에 push/merge하지 않았다. 이번 로컬 중계 변경은 이 작업 폴더에 있으며 해당 과거 보고서 게시와 별개다.
