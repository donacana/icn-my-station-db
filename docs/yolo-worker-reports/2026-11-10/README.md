> 2026-11-10 로컬 Worker 개발 보고서 사본입니다. 이번 커밋에는 문서만 포함되며, 본문의 실행 스크립트·코드·모델·원본 측정 파일은 Windows Worker 프로젝트에 있습니다.

# ICN My Station — Windows YOLO11n Worker

Windows에서 실행하는 독립적인 YOLO Worker다. **ONNX Runtime CPU를 기본으로 사용**하며, JPEG → 탐지 → ByteTrack → 현재 인원 수 → 제스처 후보 → JSON을 WebSocket으로 반환한다. React, Android, EC2, RDS, Nginx는 수정하지 않는다.

먼저 `NEXT_STEPS.md`를 확인한다. 실제 EC2 연결과 최종 학습 모델 검증은 미완료다.

## 1. 현재 실행 환경

- 프로젝트: `D:\ICN-YOLOyolo-worker`
- Python 3.12.10
- `.venv`: ONNX 전용. Torch/Ultralytics가 설치되어 있지 않아도 실행
- `.venv-model`: 모델 변환 및 선택형 Torch 실행
- 기본 모델: 공식 YOLO11n COCO를 직접 ONNX로 내보낸 `models/yolo11n.onnx`
- 기본값: 416×416, FP32, ONNX intra-op 4 / inter-op 1, 입력 처리 제한 3 FPS
- `models/best.onnx`가 존재하면 우선 사용. 기본 경로에 학습 모델이 없을 때만 데모 모델로 대체하고 경고를 출력
- 잘못 지정한 커스텀 경로에는 조용한 대체 동작 없음

## 2. 설치와 실행

```powershell
Set-Location 'D:\ICN-YOLOyolo-worker'
.\setup.ps1
.\demo.ps1
.\test.ps1 -Real
```

현재 PC에는 환경과 모델이 준비되어 있다. `setup.ps1`은 기존 환경을 삭제하지 않고 필요한 패키지와 import를 확인한다. PowerShell 실행 정책을 변경하거나 우회하지 않는다. 정책 때문에 스크립트가 막히면 동일 Python 모듈 명령을 직접 사용한다.

```powershell
.\.venv\Scripts\python.exe -m scripts.smoke
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m tools.process_demo
```

`demo.ps1`은 하나의 Python 프로세스 안에서 로컬 Mock과 실제 Worker 코드를 비동기로 실행하고 소켓·추론 작업을 정리한다. `tools.process_demo`는 Mock/Worker CLI를 별도 자식 프로세스로 띄워 종료까지 검증한다. 실패 시 비정상 종료 코드가 반환된다.

### Mock과 Worker를 직접 실행

첫 번째 PowerShell:

```powershell
.\.venv\Scripts\python.exe -m mock_server.server --frames 30 --disconnect-after 3
```

두 번째 PowerShell:

```powershell
.\run.ps1
```

Worker는 Ctrl+C로 종료한다. Mock이 정해진 프레임 검증을 마치고 종료되면 Worker는 재접속을 시도한다. 유한 실행 확인은 `.\run.ps1 -RunSeconds 10`을 사용한다.

Mock은 127.0.0.1에만 바인딩한다. 포트 기본값은 8765다. 사용자 이미지/로컬 동영상을 명시적으로 지정할 수 있다.

```powershell
.\.venv\Scripts\python.exe -m mock_server.server --image 'D:\ICN-YOLOyolo-worker\tests\assets\astronaut.png' --fps 3
.\.venv\Scripts\python.exe -m mock_server.server --generated
# 승인된 로컬 파일만 사용: --video '프로젝트 내부 테스트 동영상 경로'
```

`--generated`는 빈 합성 이미지라 사람 수 0이 정상이다. 실제 사람 검출 검증에는 기본 NASA 인물 사진을 사용한다. 카메라 장치를 자동으로 열지 않는다.

## 3. 모델 준비

새 PC에서 ONNX 모델이 없다면 모델 준비 환경을 별도로 만든다. 현재 준비된 파일을 다시 다운로드/변환할 필요는 없다.

```powershell
py -3.12 -m venv .venv-model
.\.venv-model\Scripts\python.exe -m pip install torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cu118
.\.venv-model\Scripts\python.exe -m pip install -r requirements-torch.txt
.\.venv-model\Scripts\python.exe -m scripts.download_model
.\.venv-model\Scripts\python.exe -m tools.export_onnx
.\.venv\Scripts\python.exe -m tools.prepare_sample
.\.venv\Scripts\python.exe -m tools.inspect_model
```

GPU가 필요 없으면 첫 설치 명령의 인덱스를 `https://download.pytorch.org/whl/cpu`로 바꾼다. GTX 1050에는 실제 검증된 cu118 조합을 사용했다. 다른 GPU에서 이 조합이 최적이라고 주장하지 않는다. 모델 준비 환경의 CUDA 패키지는 약 2.8GB 다운로드가 필요하며, 기본 Worker에는 설치하지 않는다.

`tools/export_onnx.py`는 CPU에서 batch=1, FP32, opset 17, dynamic 입력, NMS 미포함으로 내보낸다. `--fixed --imgsz 640`을 지정하면 고정 입력으로 내보낼 수 있다. 기존 같은 이름의 ONNX를 교체하므로 필요한 모델은 별도 경로로 보관한다.

공식 모델 출처와 다운로드 크기·SHA256은 `models/source.json`, 변환 계보는 `models/yolo11n.source.json`에 기록된다. 현재 .pt 크기는 5,613,764 bytes다.

## 4. 설정

`.env.example`을 참고해 `.env`를 만든다. 환경변수가 `.env`보다 우선한다. 경로는 실행 디렉터리와 관계없이 프로젝트 기준으로 해석한다. `.env`와 모델 파일은 Git 제외 대상이다.

| 설정 | 기본값 / 의미 |
|---|---|
| INFERENCE_BACKEND | onnx_cpu / torch_cpu / torch_cuda / auto |
| ONNX_MODEL_PATH | models/best.onnx |
| TORCH_MODEL_PATH | models/best.pt |
| CLASS_MAP_PATH | 선택: models/data.yaml |
| CAMERA_ID | DEMO_T1_3 |
| WS_URL | 로컬 ws://127.0.0.1:8765/ws/yolo/worker |
| WS_TOKEN | Mock의 Authorization: Bearer 인증용, 로그 제외 |
| YOLO_CONF / YOLO_IOU | 0.35 / 0.45 |
| YOLO_IMGSZ / YOLO_MAX_FPS | 416 / 3 |
| ONNX_INTRA_OP_THREADS / ONNX_INTER_OP_THREADS | 4 / 1 |
| ENABLE_TRACKING / ENABLE_GESTURE | true / true; 클래스 없으면 제스처 비활성 |
| GESTURE_WINDOW_SECONDS / GESTURE_COOLDOWN_SECONDS | 2 / 30 |
| GESTURE_CONF | 0.6 |
| GESTURE_OPEN_CLASS / GESTURE_FIST_CLASS | help_open / help_fist; 담당자 확인 후 명시 변경 |
| ALLOW_CUDA_AUTO | false |
| CUDA_MIN_FREE_MB | 512 |
| MAX_FRAME_AGE_SECONDS / OFFLINE_SECONDS | 5 / 10 |
| MOCK_MODE | true; 실제 계약 어댑터 미구현 상태에서 false 거부 |

auto는 사용 가능한 ONNX 모델을 우선한다. ONNX 파일이 없을 때 Torch CPU를 검토하며, CUDA는 ALLOW_CUDA_AUTO=true와 실제 연산·메모리 점검을 통과해야 선택한다. 선택 이유를 로그에 남긴다. 선택한 엔진의 모델 로딩/추론이 실패하면 실패 상태로 종료한다. 매 프레임 교체하거나 조용히 다른 엔진으로 전환하지 않는다.

### 선택형 PyTorch 실행

```powershell
$env:INFERENCE_BACKEND='torch_cuda'
$env:YOLO_IMGSZ='320'
.\run.ps1 -Torch
# 종료 후 기본 실행으로 복귀
Remove-Item Env:INFERENCE_BACKEND
Remove-Item Env:YOLO_IMGSZ
```

Torch CPU는 `INFERENCE_BACKEND=torch_cpu`를 사용한다. FP16은 적용하지 않았다. 첫 GPU 추론 전에 kernel/Compute Capability/arch 목록/VRAM을 확인한다. OOM이면 모델 자원을 해제하고 종료하며, ONNX CPU로 설정을 바꿔 재시작한다. 다른 Windows 프로세스를 종료하지 않는다.

## 5. 모델 교체와 지원 형식

`best.onnx`, `best.pt`, `data.yaml`을 `models/`에 복사한 뒤 검사한다. 신뢰할 수 있는 학습 담당자의 .pt만 사용한다.

ONNX 지원 범위:

- 단일 FP32 NCHW 입력, batch=1, 채널 3, Detect 모델
- 고정 H/W 또는 동적 H/W. 고정 640이면 YOLO_IMGSZ=416이어도 실제 입력은 640
- 모델 메타데이터의 names, task=detect, Ultralytics description, args.nms 확인
- NMS 미포함: `[1, 4+클래스수, 예측수]`, 입력 픽셀 기준 중심 xywh, confidence 필터 + 클래스별 NMS
- NMS 포함: `[1, N, 6]`, xyxy/conf/classId, 중복 NMS 없음
- 그 외 다중 출력, segmentation/pose, FP16/INT8, 임의 출력 포맷은 오류. 해당 모델에 맞는 어댑터가 필요

모델의 구조를 시작 시 실제 0 입력으로 검사한다. 클래스 수와 출력 채널이 다르거나 data.yaml과 메타데이터가 다르면 오류다. 실제 person의 ID를 메타데이터에서 읽으며 0으로 고정하지 않는다. head는 존재할 때만 반환하고 인원 수에 가산하지 않는다. 무기·화재 등 범위 밖 클래스는 Worker 결과에서 제외한다.

현재 실물 검증은 동적 NMS 미포함 모델이다. 고정 입력과 NMS 포함 후처리는 단위 테스트로 검증했으며 최종 학습 모델 수령 후 실제 파일 검증이 필요하다.

## 6. 추적·인원 수·제스처

`trackers==2.7.0`의 실제 `ByteTrackTracker.update(supervision.Detections, timestamp=...)` API를 사용한다. person만 추적하며 ID는 프로세스 내 단조 증가 값을 매핑한다. 카메라별 상태와 세션을 분리하고, 연결/카메라 세션 변경 시 상태를 지운다. 현재 Worker 연결은 설정된 카메라 1대만 허용한다. 추적 모듈은 최대 8개 카메라를 분리할 수 있다.

추적의 신규 트랙 활성 임계값은 max(YOLO_CONF, 0.6)다. YOLO_CONF 이상 0.6 미만 검출은 기존 트랙 연결에 사용될 수 있다. 초기 프레임에서 trackId=null이어도 personCount는 실제 검출 수로 계산한다. 무검출 프레임에 이전 트랙을 인원 수로 계속 더하지 않는다. 짧은 가림 상태는 최대 2초 보존하며, 유휴 시에도 정리한다.

LIVE 인원 수는 현재 검출 수다. STALE/OFFLINE은 별도 상태 메시지와 personCount=null을 보내며, 0명과 구별한다. trackId는 신원이 아니며 영구 저장하지 않는다.

제스처는 실제 모델에 설정된 두 클래스가 있어야 활성화된다. confidence, 순서, 시간 역전, 2초 제한, 30초 cooldown을 검사한다. 유일한 person 박스에 속한 하나의 손 후보가 짧은 간격에 작은 이동·비슷한 크기로 연결될 때만 후보를 만든다. 중첩 인물/여러 손/큰 이동은 거부한다. 사람 ID를 손 ID로 복사하지 않는다.

이 공간 연결은 검증 완료된 손 추적기가 아니다. 이벤트는 항상 `help_candidate`, `confirmed=false`다. 실제 손동작 인식과 긴급 판단 정확도는 미검증이다. COCO 모델에는 손동작 클래스가 없어 events=[]다.

## 7. 처리 및 보호 정책

- 수신과 추론을 분리하고 추론은 작업 스레드에서 직렬 실행
- 카메라당 대기 JPEG 1개 + 현재 처리 중 1개. 대기 프레임은 최신 프레임으로 교체
- 연결 UUID, camera generation, 단조 frameId/캡처 시간 검사
- 5초 초과 오래된 프레임/결과 및 5초 초과 미래 캡처 시간 거부
- JPEG 최대 8MiB, 헤더 검사 후 최대 8,294,400 픽셀 디코딩
- 바이너리/원본 영상/토큰/박스·트랙 상세를 로그나 결과 보고서에 저장하지 않음
- 공개 테스트 사진의 벤치마크 박스만 비교용 보고서에 저장. 사용자 이미지 입력은 상세 저장 안 함
- WebSocket Ping/Pong 20초, 연결 timeout 10초, 지수 backoff 0.5~30초에 jitter
- 인증 거부는 무한 재시도하지 않고 종료
- Ctrl+C는 수신 중단, 진행 중 추론 회수, 소켓/추적기/엔진 정리

`ws://`는 암호화되지 않는다. 현재 로컬 테스트 전용이며, 실제 운영은 계약에 맞는 `wss://` 사용을 권장한다. 실제 EC2 주소/인증정보를 자동으로 검색하거나 연결하지 않는다.

## 8. 테스트와 벤치마크

```powershell
.\test.ps1
.\test.ps1 -Real
.\.venv-model\Scripts\python.exe -m pytest -q -m torch
.\benchmark.ps1 -Backend onnx_cpu -ImageSize 416 -Threads 4
.\benchmark.ps1 -Backend torch_cpu -ImageSize 416
.\benchmark.ps1 -Backend torch_cuda -ImageSize 320
```

각 benchmark 명령은 별도 프로세스에서 한 엔진만 로드한다. 워밍업 후 최소 30초 측정한다. 다른 benchmark를 동시에 실행하지 않는다. 2/4/8 스레드와 320/416/640을 비교했으며 결과는 `reports/benchmark_*.json`, 요약은 `test_report.md`다.

`tools.compare_backends`는 ONNX 변환 출처 SHA256, 원본 .pt SHA256, 입력 이미지 해시, 해상도를 확인한 경우만 비교한다. 원본/학습 모델이 다른 결과를 비교하지 않는다. 실측 FPS는 단일 반복 사진의 처리량이며 네트워크·카메라 실시간 성능이나 정확도를 보장하지 않는다.

## 9. 파일 구성

- `app/config.py`, `inference_base.py`, `inference_manager.py`: 설정과 단일 엔진 선택
- `onnx_engine.py`, `torch_engine.py`, `preprocessing.py`, `postprocessing.py`: 탐지
- `pipeline.py`, `tracking.py`, `counting.py`, `gesture.py`: 공통 처리
- `protocol.py`, `ws_client.py`, `frame_buffer.py`: 임시 계약, 통신, 적체 방지
- `metrics.py`, `logging_config.py`, `main.py`: 측정, 로그, 시작/종료
- `mock_server/`: 로컬 테스트 서버와 이미지/동영상 소스
- `tools/`: 모델 준비·검사·하드웨어·벤치마크·독립 프로세스 검증
- `tests/`: 모델 없는 테스트와 실제 ONNX/선택형 Torch 테스트
- `requirements-lock.txt`, `requirements-torch-lock.txt`: 실측 환경 전체 패키지 버전

`trackers`와 `supervision`의 배포 의존성이 `opencv-python`이므로 최종 환경은 이 패키지 하나를 사용한다. 요청된 headless 패키지와 동시에 설치하면 cv2 파일이 충돌하므로 공존시키지 않았다. 프로그램은 GUI/카메라 API를 사용하지 않고 터미널에서 동작한다. 두 환경 모두 `pip check`를 통과했다.

## 10. 문제 해결

- 모델 없음: `tools.prepare_sample`, 모델 다운로드/변환 절차 확인. 자동 대용량 다운로드 없음
- 클래스 오류: data.yaml와 모델 내 names 대조. 이름 자동 변환 금지
- 연결 실패: 로컬 Mock 실행 여부와 포트 확인. EC2 연결 성공으로 해석하지 않음
- CUDA 실패/OOM: ONNX CPU로 설정 후 재시작. Windows 보안/전원/프로세스 변경 불필요
- `libpng ... iCCP` 경고: 공개 샘플의 색상 프로파일 경고. 실제 디코딩/탐지 테스트는 통과
- 실제 EC2: `integration_report.md`의 계약 확인 후 어댑터 구현 필요. URL만 교체해서는 연결할 수 없음

## 참고 자료

- [ONNX Runtime Python API](https://onnxruntime.ai/docs/api/python/api_summary.html)
- [Ultralytics YOLO11](https://docs.ultralytics.com/models/yolo11/), [ONNX export](https://docs.ultralytics.com/modes/export/)
- [Roboflow trackers](https://github.com/roboflow/trackers)
- [PyTorch 공식 2.7.1 설치 조합](https://pytorch.org/get-started/previous-versions/)
- [NASA 샘플 출처/공개 사용 정보](https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.astronaut)

외부 라이브러리와 가중치의 라이선스는 해당 배포본을 따른다. Ultralytics 공식 저장소의 라이선스는 AGPL-3.0이며, 공개 이미지의 별도 출처는 `tests/assets/SOURCE.md`에 기록했다.
