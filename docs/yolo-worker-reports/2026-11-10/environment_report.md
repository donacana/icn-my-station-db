> 2026-11-10 로컬 Worker 개발 보고서 사본입니다. 이번 커밋에는 문서만 포함되며, 본문의 실행 스크립트·코드·모델·원본 측정 파일은 Windows Worker 프로젝트에 있습니다.

# 환경 보고서

측정일: 2026-11-10 KST. 실행 시점의 측정이며 가용 메모리는 달라질 수 있다.

| 항목 | 실제 확인 값 |
|---|---|
| OS | Windows-11-10.0.26200-SP0 (Windows 11 Education) |
| CPU | Intel(R) Core(TM) i7-14700 |
| 물리 코어 / 논리 스레드 | 20 / 28 |
| RAM 전체 / 가용 | 15.68 / 2.72 GiB |
| GPU / VRAM 전체·사용 / 드라이버 | NVIDIA GeForce GTX 1050, 2048 MiB, 1366 MiB, 582.28 |
| D: 여유 공간 | 885.51 GiB |
| Python | 3.12.10 x64 |
| 기본 실행 환경 | .venv / ONNX Runtime CPU / Torch 미설치 |
| 선택 환경 | .venv-model / 모델 변환 + Torch CPU/CUDA |
| pip | 25.0.1 |
| 개발 도구 | Python launcher, git, uv 확인. nvcc/cmake는 PATH에서 확인되지 않음 |

## CUDA 실제 검증

- PyTorch: 2.7.1+cu118, 빌드 CUDA: 11.8
- torch.cuda.is_available(): True
- Compute Capability: [6, 1]
- 아키텍처: sm_37, sm_50, sm_60, sm_61, sm_70, sm_75, sm_80, sm_86, sm_90, compute_37
- 실제 CUDA 행렬 연산: True
- Torch 보고 freeMiB: 1589.9091796875; NVIDIA-SMI freeMiB: 545.0
- NVIDIA-SMI의 CUDA 13.0 표시는 드라이버 지원 상한이다. 설치된 PyTorch 런타임은 CUDA 11.8이다.
- Windows WDDM에서 Torch와 NVIDIA-SMI의 메모리 수치는 다를 수 있다. 선택 시 두 값 중 작은 가용량을 사용한다.
- GTX 1050에서 FP32 320/416 실제 YOLO11n 추론과 Mock 통신 성공. 자세한 실측은 test_report.md.
- 시스템 프로세스를 종료하거나 전원·보안·방화벽 설정을 변경하지 않았다.

## 주요 패키지

| 패키지 | ONNX .venv |
|---|---|
| onnxruntime | 1.23.2 |
| numpy | 2.2.6 |
| opencv-python | 4.12.0.88 |
| trackers | 2.7.0 |
| supervision | 0.31.6 |
| websockets | 15.0.1 |
| python-dotenv | 1.2.1 |
| pytest | 8.4.2 |
| psutil | 7.1.3 |
| pillow | 12.0.0 |
| PyYAML | 6.0.3 |

선택 환경: torch 2.7.1+cu118 / torchvision 0.22.1+cu118 / ultralytics 8.3.228 / onnx 1.19.1.
선택 환경 Pillow는 13.0.0으로 검증됐고, 기본 환경은 12.0.0이다. 전체 정확한 버전은 requirements-lock.txt와 requirements-torch-lock.txt에 기록했다.
두 환경에서 pip check 성공. trackers/supervision의 opencv-python 의존성에 맞춰 headless와 중복 설치하지 않았다.
설치된 API를 inspect.signature 및 소스 확인 후 사용했다. 기본 ONNX 테스트에서는 torch/ultralytics가 sys.modules에 없는 상태도 검증했다.

원본 근거: reports/hardware.json, reports/hardware_torch.json. 재검사는 tools/inspect_hardware.py로 수행한다.
