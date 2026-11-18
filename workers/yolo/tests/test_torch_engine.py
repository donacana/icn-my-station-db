import importlib.util
import pytest
from dataclasses import replace
from app.config import Settings


def test_torch_optional_import():
    # Module itself must not import Torch into the ONNX runtime.
    import app.torch_engine
    assert callable(app.torch_engine.check_cuda_compatibility)


@pytest.mark.torch
@pytest.mark.real
def test_torch_cpu_person(sample):
    if importlib.util.find_spec("torch") is None:
        pytest.skip("Optional Torch not installed in ONNX environment")
    from app.torch_engine import TorchInferenceEngine
    from app.preprocessing import decode_jpeg
    engine=TorchInferenceEngine(replace(Settings(),imgsz=320),"torch_cpu")
    try:
        assert any(d.class_name=="person" for d in engine.infer(decode_jpeg(sample)))
    finally: engine.close()
