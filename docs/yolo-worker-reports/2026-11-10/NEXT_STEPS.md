> 2026-11-10 로컬 Worker 개발 보고서 사본입니다. 이번 커밋에는 문서만 포함되며, 본문의 실행 스크립트·코드·모델·원본 측정 파일은 Windows Worker 프로젝트에 있습니다.

# 돌아온 후 가장 먼저 확인할 내용

작업 위치: `D:\ICN-YOLOyolo-worker`
기본 실행: **YOLO11n / ONNX Runtime CPU / 416 / 4스레드**

## 1. 지금 바로 전체 흐름 확인

PowerShell에서 다음 명령을 실행한다. 가상환경 활성화는 필요 없다.

```powershell
Set-Location 'D:\ICN-YOLOyolo-worker'
.\demo.ps1
.\test.ps1 -Real
```

`demo.ps1`은 로컬 Mock 시작 → Worker 연결 → 실제 JPEG 사람 탐지 → ByteTrack → 인원 계산 → JSON 검증 → 연결 강제 종료 → 재접속 → 정상 종료를 자동으로 수행한다. 테스트 사진에서 사람 1명, 연결 2회, 응답 18개가 정상 결과다. 사진은 NASA 공개 테스트 자료이며 실제 카메라를 켜지 않는다.

서버와 Worker를 별도 프로세스로 검증하려면:

```powershell
.\.venv\Scripts\python.exe -m tools.process_demo
```

이 검증은 기본적으로 응답 12개, 연결 2회 및 두 프로세스 종료 코드 0을 확인한다. 작업 종료 후 서버는 계속 실행되어 있지 않다.

## 2. 학습 담당자에게 받을 파일

- 동일 학습 결과의 `best.onnx`, `best.pt`, `data.yaml`
- YOLO11n Detect 모델 여부, 학습/내보내기 버전, 입력 크기, FP32 여부
- ONNX NMS 포함 여부, 클래스 목록, 클래스별 의미
- 실제 손동작 검증용 동영상과 사용 권한

신뢰할 수 있는 파일만 `models/`에 복사한다. 현재 학습 모델은 없으며 COCO YOLO11n으로 사람 탐지만 검증했다.

`.env.example`을 `.env`로 복사하고 다음 값을 검토한다. 기존 `.env`가 있다면 덮어쓰지 않는다.

```env
INFERENCE_BACKEND=onnx_cpu
ONNX_MODEL_PATH=models/best.onnx
TORCH_MODEL_PATH=models/best.pt
CLASS_MAP_PATH=models/data.yaml
```

```powershell
.\.venv\Scripts\python.exe -m tools.inspect_model
.\demo.ps1
```

데모는 자체 설정을 사용하는 COCO 회귀 검증이므로, 커스텀 모델의 해상도·클래스 설정은 `tools.inspect_model`과 별도 Mock/Worker 실행으로도 확인한다. `models/best.onnx`가 있으면 데모도 이 모델을 사용한다. 예제 사진에서 검출되지 않는 학습 모델은 데모가 실패할 수 있다.

`person`을 다른 이름에서 자동 추정하지 않는다. 손동작 클래스가 다른 이름이면 담당자 확인 후 `GESTURE_OPEN_CLASS`, `GESTURE_FIST_CLASS`를 명시한다. 모델 메타데이터와 `data.yaml`이 다르면 실행을 중단한다.

## 3. 민규에게 실제 WebSocket 계약 받기

`integration_report.md`의 표를 전달해 주소·인증·바이너리·응답·세션 계약을 확인한다.

**현재 코드는 Mock 규격만 구현했다. EC2 주소만 넣으면 바로 연결되는 상태는 아니다.** 실제 계약에 맞춰 `app/protocol.py`의 별도 어댑터와 설정 선택을 구현해야 한다. 현재 외부 주소와 `MOCK_MODE=false`는 명시적으로 거부한다. 이 제한은 미확정 프로토콜을 운영 서버에 보내지 않기 위한 것이다.

## 4. 실제 연동은 계약 적용 후 사용자가 진행

1. 최종 모델 검사 및 공개/승인된 테스트 프레임으로 추론 확인
2. 백엔드 계약 어댑터 적용 및 계약 테스트 작성
3. 승인된 테스트 EC2 주소, cameraId, 인증 토큰을 `.env`에 입력
4. 가능하면 `wss://` 사용
5. Worker 실행 → 휴대폰 카메라 송출 → 기존 대시보드 확인
6. 사람 수·박스·세션 변경·카메라 OFFLINE 상태 확인
7. 실제 도움 요청 동작으로 오탐·미탐·동일 손 연결 검증

제스처는 현재 합성 데이터 단위 테스트만 통과했다. 모델에 두 클래스가 있으면 보수적인 공간 연결로 `help_candidate`를 만들 수 있지만, `confirmed=false`이며 긴급 상황 확정 기능은 아니다. 정확도 검증 전 운영 긴급 알림으로 바로 연결하지 않는다.

## 5. 선택형 GPU 확인

GTX 1050의 CUDA 연산과 실제 YOLO11n 추론은 이 PC에서 성공했다. 그러나 가용 VRAM은 실행 시점마다 달라진다. 기본 ONNX CPU 설정을 유지해도 시연 목표를 충족한다.

```powershell
.\demo.ps1 -Backend torch_cuda
.\benchmark.ps1 -Backend torch_cuda -ImageSize 320
```

GPU 실패 시 `.env`를 `INFERENCE_BACKEND=onnx_cpu`로 바꾸고 재시작한다. 실행 중 몰래 백엔드를 바꾸지 않는다.

상세 실측/테스트 결과: `test_report.md`
설치 및 문제 해결: `README.md`
환경/패키지 버전: `environment_report.md`
