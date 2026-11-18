"""Build reports from recorded measurements; never fabricate missing results."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json
import xml.etree.ElementTree as ET
from app import ROOT


def read(name):
    return json.loads((ROOT/"reports"/name).read_text(encoding="utf-8"))


def tests(name):
    root=ET.parse(ROOT/"reports"/name).getroot()
    cases=list(root.iter("testcase"))
    failed=sum(c.find("failure") is not None or c.find("error") is not None for c in cases)
    skipped=sum(c.find("skipped") is not None for c in cases)
    return len(cases)-failed-skipped,failed,skipped


def main():
    hardware=read("hardware.json")
    cuda=read("hardware_torch.json")["cuda"]
    lines=["# 환경 보고서", "", "측정일: 2026-11-10 KST. 실행 시점의 측정이며 가용 메모리는 달라질 수 있다.", "",
        "| 항목 | 실제 확인 값 |", "|---|---|",
        f"| OS | {hardware['os']} (Windows 11 Education) |",
        f"| CPU | {hardware['cpu']} |",
        f"| 물리 코어 / 논리 스레드 | {hardware['physicalCores']} / {hardware['logicalThreads']} |",
        f"| RAM 전체 / 가용 | {hardware['totalRamGiB']:.2f} / {hardware['availableRamGiB']:.2f} GiB |",
        f"| GPU / VRAM 전체·사용 / 드라이버 | {hardware['gpu']} |",
        f"| D: 여유 공간 | {hardware['diskFreeGiB']:.2f} GiB |",
        f"| Python | {hardware['python'].split(' (')[0]} x64 |",
        "| 기본 실행 환경 | .venv / ONNX Runtime CPU / Torch 미설치 |",
        "| 선택 환경 | .venv-model / 모델 변환 + Torch CPU/CUDA |",
        "| pip | 25.0.1 |", "| 개발 도구 | Python launcher, git, uv 확인. nvcc/cmake는 PATH에서 확인되지 않음 |", "",
        "## CUDA 실제 검증", "",
        f"- PyTorch: {cuda.get('torchVersion')}, 빌드 CUDA: {cuda.get('builtCuda')}",
        f"- torch.cuda.is_available(): {cuda.get('available')}",
        f"- Compute Capability: {cuda.get('capability')}",
        f"- 아키텍처: {', '.join(cuda.get('architectures',[]))}",
        f"- 실제 CUDA 행렬 연산: {cuda.get('kernelSucceeded')}",
        f"- Torch 보고 freeMiB: {cuda.get('freeMiB')}; NVIDIA-SMI freeMiB: {cuda.get('nvidiaSmiFreeMiB','측정 전 보고서')}",
        "- NVIDIA-SMI의 CUDA 13.0 표시는 드라이버 지원 상한이다. 설치된 PyTorch 런타임은 CUDA 11.8이다.",
        "- Windows WDDM에서 Torch와 NVIDIA-SMI의 메모리 수치는 다를 수 있다. 선택 시 두 값 중 작은 가용량을 사용한다.",
        "- GTX 1050에서 FP32 320/416 실제 YOLO11n 추론과 Mock 통신 성공. 자세한 실측은 test_report.md.",
        "- 시스템 프로세스를 종료하거나 전원·보안·방화벽 설정을 변경하지 않았다.", "",
        "## 주요 패키지", "", "| 패키지 | ONNX .venv |", "|---|---|"]
    for key in ["onnxruntime","numpy","opencv-python","trackers","supervision","websockets","python-dotenv","pytest","psutil","pillow","PyYAML"]:
        lines.append(f"| {key} | {hardware['packages'].get(key,'미확인')} |")
    lines += ["", "선택 환경: torch 2.7.1+cu118 / torchvision 0.22.1+cu118 / ultralytics 8.3.228 / onnx 1.19.1.",
        "선택 환경 Pillow는 13.0.0으로 검증됐고, 기본 환경은 12.0.0이다. 전체 정확한 버전은 requirements-lock.txt와 requirements-torch-lock.txt에 기록했다.",
        "두 환경에서 pip check 성공. trackers/supervision의 opencv-python 의존성에 맞춰 headless와 중복 설치하지 않았다.",
        "설치된 API를 inspect.signature 및 소스 확인 후 사용했다. 기본 ONNX 테스트에서는 torch/ultralytics가 sys.modules에 없는 상태도 검증했다.",
        "", "원본 근거: reports/hardware.json, reports/hardware_torch.json. 재검사는 tools/inspect_hardware.py로 수행한다."]
    (ROOT/"environment_report.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    passed,failed,skipped=tests("pytest.xml")
    tp,tf,ts=tests("pytest_torch.xml")
    lines=["# 테스트 및 실측 보고서", "", "실행일: 2026-11-10 KST. 아래 수치는 이 PC에서 직접 실행한 결과다.", "",
        "## 자동 테스트", "",
        f"- 기본 ONNX 환경: **{passed} 통과 / {failed} 실패 / {skipped} 제외** (`reports/pytest.xml`)",
        f"- 별도 Torch 환경: **{tp} 통과 / {tf} 실패 / {ts} 제외** (`reports/pytest_torch.xml`, -m torch 선택)",
        "- 기본 환경의 제외 항목은 Torch 미설치로 인한 선택형 실모델 테스트다. 같은 항목을 별도 환경에서 통과했다. 다른 테스트의 재실행을 새 성공 건수로 중복 집계하지 않았다.",
        "- 검증 범위: 설정/클래스 매핑, JPEG, Letterbox 역변환, confidence 및 클래스별 NMS, 실제 320/416/640 ONNX person 탐지, ByteTrack 신규·유지·가림·만료·세션 분리, 인원 수, 합성 제스처, 바이너리/JSON, 최신 버퍼, 인증 성공·거부, 접속 실패·재시도, 자동 재접속, STALE/OFFLINE, 이전 세션 결과 폐기, 실패 엔진 종료, 비밀 로그 제거.",
        "", "## 실제 Mock 전체 파이프라인", "",
        "입력: 공개 NASA 사진을 비율 유지해 640×360으로 구성한 JPEG, 3 FPS. 최종 best 모델이 아닌 동일 공식 YOLO11n 계열.", "",
        "| 백엔드 | 연결 | JSON 응답 | 사람 수 | 실측 처리 FPS | 평균 추론 ms | 평균 JPEG ms | 평균 전체 처리 ms | RAM MiB | 오류 |",
        "|---|---:|---:|---|---:|---:|---:|---:|---:|---|"]
    for backend in ("onnx_cpu","torch_cpu","torch_cuda"):
        r=read(f"smoke_{backend}.json");m=r["metrics"]
        lines.append(f"| {backend} | {r['connections']} | {r['responses']} | {r['personCounts']} | {m['processingFps']:.2f} | {m['inferenceMs']:.2f} | {m['decodeMs']:.2f} | {m['processingMs']:.2f} | {m['rssMiB']:.1f} | {r['errors']} |")
    process=read("process_demo.json")
    lines += ["", "모든 백엔드에서 강제 close 1012 이후 재접속했다. 초기 프레임은 미확정 trackId=null이며 후속 프레임에 ByteTrack ID가 부여됐다. 현재 인원 수는 초기 프레임부터 검출 수로 반환한다.",
        f"별도 Mock/Worker 프로세스 테스트: {process}. 서버/Worker가 실제 독립 실행되고 종료 코드 0 및 bounded shutdown을 확인했다.",
        "30개 프레임을 빠르게 전송하고 추론에 인위적 지연을 준 자동 테스트에서는 대기 폐기 10개 초과, 버퍼 최대 1개 및 최신 frameId=29 반환을 확인했다.",
        "단기간 표본이라 첫 프레임과 측정 구간 경계 때문에 처리 FPS가 3보다 약간 높게 표시될 수 있다. 장시간 처리 성능 보장은 아니다.",
        "", "## 30초 이상 백엔드 벤치마크", "",
        "각 조건은 독립 프로세스에서 실행하고 5회 워밍업 뒤 30초 이상 측정했다. 모든 비교는 같은 공개 입력과 동일 .pt에서 변환한 .onnx를 사용한다. 네트워크·JPEG 디코딩·ByteTrack은 아래 추론 벤치마크에 포함되지 않는다. 엔진의 전처리·추론·후처리는 포함된다.",
        "", "| 백엔드 | 크기 | 스레드 | 로딩 ms | 최초 추론 ms | 평균 ms | 최소 ms | 최대 ms | P95 ms | FPS | 측정 초 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    rows=[]
    for path in sorted((ROOT/"reports").glob("benchmark_*.json")):
        r=json.loads(path.read_text()); rows.append(r)
        if r["status"]!="passed":
            lines.append(f"| {r['backend']} | {r['requestedImgsz']} | {r['threads']} | {r['status']}: {r.get('reason')} | | | | | | | |")
            continue
        lines.append(f"| {r['backend']} | {r['requestedImgsz']} | {r['threads']} | {r['loadMs']:.2f} | {r['initialInferenceMs']:.2f} | {r['meanMs']:.2f} | {r['minMs']:.2f} | {r['maxMs']:.2f} | {r['p95Ms']:.2f} | {r['fps']:.2f} | {r['durationSeconds']:.2f} |")
    lines += ["", "ONNX 로딩 시간에는 세션 생성과 출력 검증용 0 입력 실행이 포함된다. Torch는 첫 추론에 predictor 준비·GPU 워밍업이 포함되어 최초 지연이 크다. 따라서 로딩/최초 추론을 따로 기록했다.",
        "", "| 백엔드/크기/스레드 | 프로세스 CPU % | 28스레드 대비 환산 % | 관측 최대 RSS MiB | GPU 사용률 % (종료 시점) | GPU 전체 사용 MiB (종료 시점) |",
        "|---|---:|---:|---:|---:|---:|"]
    for r in rows:
        if r["status"]!="passed": continue
        gpu=r["resources"].get("gpu") or {}
        lines.append(f"| {r['backend']}/{r['requestedImgsz']}/{r['threads']} | {r['cpuProcessPercent']:.1f} | {r['cpuMachineEquivalentPercent']:.2f} | {r['peakRssMiB']:.1f} | {gpu.get('utilizationPercent','미측정')} | {gpu.get('usedMiB','미측정')} |")
    lines += ["", "프로세스 CPU 100%는 논리 코어 하나를 사용하는 수준이다. 환산 값은 이 PC 전체 CPU 실측 사용률이 아닌 process CPU/28이다. GPU 수치는 NVIDIA-SMI의 종료 시점 장치 전체 스냅샷으로, 다른 Windows 프로그램을 포함하며 Worker 전용·평균·최대값이 아니다.",
        "기본 설정은 ONNX 416/4스레드를 유지했다. 8스레드의 평균 속도 이득은 작고 CPU 사용량 및 P95가 증가했다. 320은 빠르지만 실제 혼잡 장면의 정확도를 검증하지 않았으므로 기본 해상도를 자동으로 낮추지 않았다.",
        "", "## 동일 모델 탐지 결과 비교", ""]
    for r in read("backend_comparison.json"):
        lines.append(f"- ONNX ↔ {r['backend']}: 동일 가중치/입력 해시 검증, 박스 {r['matched']}/{r['onnxDetections']} 매칭; IoU/점수차 {r['pairs']}")
    lines += ["", "한 장의 공개 이미지 비교이며 데이터셋 정확도·mAP·실제 혼잡 인원 정확도 검증이 아니다. 샘플 원본 해상도에서는 추가 person 오탐이 나타난 초기 실행도 있었으므로 이 결과를 일반 정확도로 확대 해석하지 않는다.",
        "", "## 수정한 문제와 남은 사항", "",
        "- 초기 Mock 검증에서 첫 프레임에도 trackId가 있어야 한다고 가정해 실패했다. 실제 API의 초기 미확정 ID 동작을 확인하고, 첫 프레임 인원 계산과 후속 ID 부여를 구분해 수정했다.",
        "- OpenCV headless/일반 패키지 중복 설치를 제거하고 trackers 의존성에 맞는 단일 opencv-python으로 정리했다. pip check 통과.",
        "- 선택형 GPU: 실제 CUDA 연산 및 320/416 YOLO 추론 성공. OOM을 인위적으로 유발하지 않았으며 실제 OOM 복구는 미검증. 공통 추론 실패 시 자원 해제·실패 고정·재시도 차단은 가상 실패 테스트로 검증했다.",
        "- 남은 경고: 공개 PNG의 iCCP 색상 프로파일 경고. JPEG 디코딩 및 실제 탐지에는 실패가 없었다.",
        "- 고정 입력 모델 검사는 가상 세션으로, NMS 포함 후처리는 합성 텐서로 검증했다. 해당 형식의 실제 학습 모델 테스트는 대기.",
        "- 제스처 순서/공간 연결은 가상 이벤트 테스트만 성공. 실제 학습 모델과 동영상이 없어 실제 손동작 정확도는 미검증.",
        "- 실제 EC2/Android/대시보드 연동, 최종 best 모델, 장시간 운영 및 다중 카메라는 미검증.",
        "- 코드·의존성 관련 미해결 테스트 실패는 없다. 실제 EC2 규격은 미확정이므로 연결 어댑터 적용이 남아 있다.",
        "", "실행 명령은 NEXT_STEPS.md와 README.md를 참고한다. 원본 JSON/XML은 reports/에 보존했다."]
    (ROOT/"test_report.md").write_text("\n".join(lines)+"\n",encoding="utf-8")


if __name__=="__main__":
    main()
