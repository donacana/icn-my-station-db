"""Validated project-local settings. No runtime backend switching."""
import logging
import math
import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from urllib.parse import urlsplit
from dotenv import dotenv_values,load_dotenv
from app import ROOT
from app.demo_protocol import parse_camera_id_setting

@dataclass(frozen=True)
class Settings:
    backend: str = "onnx_cpu"
    onnx_model_path: Path = ROOT / "models/best.onnx"
    torch_model_path: Path = ROOT / "models/best.pt"
    class_map_path: Path | None = None
    ws_url: str = field(default="ws://127.0.0.1:8765/ws/yolo/worker", repr=False)
    token: str = field(default="", repr=False)
    camera_id: str | int = "DEMO_T1_3"
    camera_ids: tuple[int, ...] = ()
    conf: float = 0.35
    person_conf: float = 0.25
    iou: float = 0.45
    imgsz: int = 416
    max_fps: float = 3.0
    intra_threads: int = 4
    inter_threads: int = 1
    enable_tracking: bool = True
    enable_gesture: bool = True
    gesture_window: float = 2.0
    gesture_cooldown: float = 30.0
    gesture_conf: float = 0.6
    gesture_open: str = "help_open"
    gesture_fist: str = "help_fist"
    mock_mode: bool = True
    allow_cuda_auto: bool = False
    allow_demo_model: bool = True
    min_vram_mb: int = 512
    protocol: str = "mock-v1"
    worker_id: str = "icn-windows-worker"
    model_version: str | None = None
    allow_remote_ec2: bool = False
    max_frame_age: float = 5.0
    offline_seconds: float = 10.0
    track_retention: float = 2.0
    max_pixels: int = 8_294_400
    log_result_summary: bool = False

def resolve_paths(s):
    def full(p):
        return (p if p.is_absolute() else ROOT / p).resolve() if p else None
    return replace(s, onnx_model_path=full(s.onnx_model_path), torch_model_path=full(s.torch_model_path), class_map_path=full(s.class_map_path))

def model_path(s, backend):
    ext = "onnx" if backend == "onnx_cpu" else "pt"
    path = s.onnx_model_path if ext == "onnx" else s.torch_model_path
    if path.is_file():
        return path
    if s.allow_demo_model and path.resolve() == (ROOT / f"models/best.{ext}").resolve():
        demo = ROOT / f"models/yolo11n.{ext}"
        if demo.is_file():
            logging.getLogger(__name__).warning("best.%s missing: using official YOLO11n demo; no gesture recognition", ext)
            return demo
    raise FileNotFoundError(f"Missing {ext} model; see model preparation in README")

def resolve_backend(s):
    if s.backend != "auto":
        return s.backend, "explicit configured backend"
    try:
        model_path(s, "onnx_cpu")
        return "onnx_cpu", "auto prefers available ONNX CPU model"
    except FileNotFoundError:
        model_path(s, "torch_cpu")
    if s.allow_cuda_auto:
        from app.torch_engine import check_cuda_compatibility
        if check_cuda_compatibility(s.min_vram_mb)["usable"]:
            return "torch_cuda", "CUDA explicitly enabled; kernel and VRAM preflight passed"
        return "torch_cpu", "CUDA preflight failed; CPU selected at startup"
    return "torch_cpu", "ONNX missing; CUDA auto not enabled"

def validate_settings(s):
    s = resolve_paths(s)
    if s.backend not in {"onnx_cpu", "torch_cpu", "torch_cuda", "auto"}:
        raise ValueError("Invalid INFERENCE_BACKEND")
    try:
        url = urlsplit(s.ws_url)
        valid = url.scheme in {"ws", "wss"} and url.hostname and url.port != 0
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("WS_URL must be a valid ws/wss URL")
    if url.username or url.password or url.query or url.fragment:
        raise ValueError("Use WS_TOKEN, not URL credentials/query/fragment")
    if s.protocol not in {"mock-v1", "demo-v0.3", "demo-v0.4"}:
        raise ValueError("Invalid YOLO_PROTOCOL")
    local = url.hostname in {"127.0.0.1", "localhost", "::1"}
    if s.mock_mode and not local:
        raise ValueError("MOCK_MODE is loopback only")
    if not s.mock_mode:
        if not s.allow_remote_ec2 or s.protocol not in {"demo-v0.3", "demo-v0.4"}:
            raise ValueError("Remote EC2 requires ALLOW_REMOTE_EC2=true and a demo protocol")
        if local:
            raise ValueError("Remote EC2 mode requires a non-loopback host")
        if url.path != "/ws/yolo/worker":
            raise ValueError("Remote WS_URL path must be /ws/yolo/worker")
        if not s.token:
            raise ValueError("YOLO_WORKER_TOKEN is required for remote EC2")
    if s.protocol in {"demo-v0.3", "demo-v0.4"}:
        from app.demo_protocol import validate_camera_id
        validate_camera_id(s.camera_id)
        ids = s.camera_ids or (s.camera_id,)
        if len(set(ids)) != len(ids) or not ids:
            raise ValueError("CAMERA_IDS must contain unique camera IDs")
        for camera_id in ids:
            validate_camera_id(camera_id)
    elif not isinstance(s.camera_id,str) or not s.camera_id or len(s.camera_id.encode()) > 128 or not s.camera_id.isprintable():
        raise ValueError("Invalid CAMERA_ID")
    for value in (s.conf, s.person_conf, s.iou, s.gesture_conf):
        if not math.isfinite(value) or not 0 < value <= 1:
            raise ValueError("Confidence/IoU must be in (0,1]")
    if not 32 <= s.imgsz <= 1920 or s.imgsz % 32:
        raise ValueError("YOLO_IMGSZ must be a multiple of 32 in [32,1920]")
    for value in (s.max_fps, s.max_frame_age, s.offline_seconds, s.track_retention, s.gesture_window, s.gesture_cooldown):
        if not math.isfinite(value) or value <= 0:
            raise ValueError("FPS/timeouts must be finite and positive")
    if not 1 <= s.intra_threads <= 16 or not 1 <= s.inter_threads <= 8:
        raise ValueError("Invalid ONNX thread counts")
    if s.gesture_open == s.gesture_fist or not s.gesture_open or not s.gesture_fist:
        raise ValueError("Gesture class names must be distinct")
    if s.class_map_path and not s.class_map_path.is_file():
        raise FileNotFoundError("Class mapping YAML missing")
    for path, ext in ((s.onnx_model_path, "onnx"), (s.torch_model_path, "pt")):
        if path.suffix.lower() != f".{ext}":
            raise ValueError(f"Expected .{ext} model")
    if not 1 <= s.max_pixels <= 33_177_600 or s.min_vram_mb < 1:
        raise ValueError("Invalid resource limit")
    if not s.worker_id or len(s.worker_id)>128:
        raise ValueError("Invalid WORKER_ID")
    if s.model_version is not None and (not s.model_version.strip() or len(s.model_version)>128):
        raise ValueError("Invalid WORKER_MODEL_VERSION")
    if s.protocol in {"demo-v0.3", "demo-v0.4"} and s.max_fps>3:
        raise ValueError("Demo contract requires <=3 FPS total")
    return s

def load_settings(env_file=None):
    selected_env = env_file or os.getenv("YOLO_ENV_FILE") or ROOT / ".env"
    load_dotenv(selected_env, override=False)
    file_values = dotenv_values(selected_env)
    def boolean(name, default):
        value = os.getenv(name, str(default)).lower()
        if value not in {"true", "false"}:
            raise ValueError(f"{name} must be true/false")
        return value == "true"
    mapping = os.getenv("CLASS_MAP_PATH", "")
    protocol = os.getenv("YOLO_PROTOCOL","mock-v1")
    camera_id = (parse_camera_id_setting(os.getenv("CAMERA_ID","1"))
                 if protocol in {"demo-v0.3", "demo-v0.4"} else os.getenv("CAMERA_ID","DEMO_T1_3"))
    raw_camera_ids = os.getenv("CAMERA_IDS", "")
    camera_ids = tuple(parse_camera_id_setting(value.strip()) for value in raw_camera_ids.split(",") if value.strip())
    return validate_settings(Settings(
        backend=os.getenv("INFERENCE_BACKEND", "onnx_cpu"),
        onnx_model_path=Path(os.getenv("ONNX_MODEL_PATH", "models/best.onnx")),
        torch_model_path=Path(os.getenv("TORCH_MODEL_PATH", "models/best.pt")),
        class_map_path=Path(mapping) if mapping else None,
        ws_url=os.getenv("WS_URL") or Settings().ws_url,
        token=(os.getenv("YOLO_WORKER_TOKEN") or file_values.get("YOLO_WORKER_TOKEN")
               or os.getenv("WS_TOKEN") or file_values.get("WS_TOKEN") or ""),
        camera_id=camera_id, camera_ids=camera_ids,
        protocol=protocol, worker_id=os.getenv("WORKER_ID","icn-windows-worker"),
        model_version=os.getenv("WORKER_MODEL_VERSION") or None,
        conf=float(os.getenv("YOLO_CONF", "0.35")), iou=float(os.getenv("YOLO_IOU", "0.45")),
        person_conf=float(os.getenv("PERSON_CONF", "0.25")),
        imgsz=int(os.getenv("YOLO_IMGSZ", "416")), max_fps=float(os.getenv("YOLO_MAX_FPS", "3")),
        intra_threads=int(os.getenv("ONNX_INTRA_OP_THREADS", "4")), inter_threads=int(os.getenv("ONNX_INTER_OP_THREADS", "1")),
        enable_tracking=boolean("ENABLE_TRACKING", True), enable_gesture=boolean("ENABLE_GESTURE", True),
        gesture_window=float(os.getenv("GESTURE_WINDOW_SECONDS", "2")), gesture_cooldown=float(os.getenv("GESTURE_COOLDOWN_SECONDS", "30")),
        gesture_conf=float(os.getenv("GESTURE_CONF", "0.6")),
        gesture_open=os.getenv("GESTURE_OPEN_CLASS", "help_open"), gesture_fist=os.getenv("GESTURE_FIST_CLASS", "help_fist"),
        mock_mode=boolean("MOCK_MODE", True), allow_remote_ec2=boolean("ALLOW_REMOTE_EC2", False),
        allow_demo_model=boolean("ALLOW_DEMO_MODEL_FALLBACK", True),
        allow_cuda_auto=boolean("ALLOW_CUDA_AUTO", False),
        min_vram_mb=int(os.getenv("CUDA_MIN_FREE_MB", "512")),
        max_frame_age=float(os.getenv("MAX_FRAME_AGE_SECONDS", "5")), offline_seconds=float(os.getenv("OFFLINE_SECONDS", "10")),
        log_result_summary=boolean("LOG_RESULT_SUMMARY", False),
    ))
