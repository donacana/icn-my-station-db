import os
from pathlib import Path
import pytest
from app import ROOT


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith(("YOLO_", "ONNX_", "TORCH_", "GESTURE_", "WORKER_", "ALLOW_REMOTE_")) or key in {"WS_URL", "WS_TOKEN", "CAMERA_ID", "CAMERA_IDS", "INFERENCE_BACKEND", "MOCK_MODE"}:
            if key not in {"YOLO_CONFIG_DIR", "YOLO_AUTOINSTALL"}:
                monkeypatch.delenv(key,raising=False)


@pytest.fixture
def real_model():
    if not (ROOT/"models/yolo11n.onnx").is_file():
        pytest.skip("Real ONNX model not prepared")


@pytest.fixture
def sample():
    from mock_server.frame_source import demo_jpeg
    if not (ROOT/"tests/assets/astronaut.png").is_file():
        pytest.skip("Public test image not prepared")
    return demo_jpeg()
