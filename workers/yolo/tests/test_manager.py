from dataclasses import replace
import pytest
from app.config import Settings
from app.inference_manager import InferenceManager


def test_failed_backend_never_silently_replaced(tmp_path):
    manager=InferenceManager(replace(Settings(),onnx_model_path=tmp_path/"missing.onnx"))
    with pytest.raises(FileNotFoundError): manager.initialize()
    assert manager.get_backend_status()["status"]=="failed"
    assert manager.backend=="onnx_cpu"
    with pytest.raises(RuntimeError): manager.initialize()
    manager.shutdown()


def test_logging_redacts_secrets(monkeypatch):
    import logging
    from app.logging_config import RedactingFormatter
    monkeypatch.setenv("WS_TOKEN","my-test-token")
    record=logging.LogRecord("test",40,"",0,"Error my-test-token Bearer other-token ws://localhost/x",(),None)
    text=RedactingFormatter().format(record)
    assert "my-test-token" not in text and "other-token" not in text and "ws://" not in text


def test_runtime_failure_closes_engine_and_no_retry(monkeypatch):
    import app.onnx_engine as module
    class Broken:
        closed=False
        def __init__(self,s): pass
        def load_model(self): pass
        def infer(self,image): raise RuntimeError("simulated backend allocation failure")
        def close(self): self.closed=True
    monkeypatch.setattr(module,"OnnxInferenceEngine",Broken)
    manager=InferenceManager(Settings())
    with pytest.raises(RuntimeError): manager.infer_frame(None)
    assert manager.status=="failed" and manager.engine.closed
    with pytest.raises(RuntimeError): manager.infer_frame(None)
