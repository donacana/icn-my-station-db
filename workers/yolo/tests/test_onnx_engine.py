from dataclasses import replace
import importlib.util
import sys
import pytest
from app.config import Settings
from app import ROOT
from app.onnx_engine import OnnxInferenceEngine
from app.preprocessing import decode_jpeg


def test_onnx_installed():
    assert importlib.util.find_spec("onnxruntime")


def test_bad_model(tmp_path):
    path=tmp_path/"bad.onnx"; path.write_bytes(b"bad")
    with pytest.raises(Exception): OnnxInferenceEngine(replace(Settings(),onnx_model_path=path)).load_model()


def test_fixed_shape_honored_with_mock_session(tmp_path,monkeypatch):
    import numpy as np
    from types import SimpleNamespace
    import app.onnx_engine as module
    path=tmp_path/"fixed.onnx"; path.touch()
    class Session:
        def __init__(self,*a,**kw): pass
        def get_inputs(self): return [SimpleNamespace(name="images",type="tensor(float)",shape=[1,3,640,640])]
        def get_outputs(self): return [SimpleNamespace(name="output0",shape=[1,5,1])]
        def get_modelmeta(self): return SimpleNamespace(custom_metadata_map={"task":"detect","description":"Ultralytics YOLO11n","names":"{0: 'person'}","args":"{'nms': False}"})
        def run(self,_,data):
            assert data["images"].shape==(1,3,640,640)
            return [np.zeros((1,5,1),np.float32)]
        def get_providers(self): return ["CPUExecutionProvider"]
    monkeypatch.setattr(module.ort,"InferenceSession",Session)
    engine=OnnxInferenceEngine(replace(Settings(),onnx_model_path=path,imgsz=416))
    engine.infer(np.zeros((100,100,3),np.uint8))
    assert engine.get_input_shape()==(1,3,640,640)
    assert not engine.get_model_info()["dynamicInput"]


@pytest.mark.real
@pytest.mark.parametrize("size",[320,416,640])
def test_real_person_shape_and_no_torch(real_model,sample,size):
    engine=OnnxInferenceEngine(replace(Settings(),onnx_model_path=ROOT/"models/yolo11n.onnx",imgsz=size))
    try:
        result=engine.infer(decode_jpeg(sample))
        info=engine.get_model_info()
        assert info["providers"]==["CPUExecutionProvider"]
        assert engine.get_input_shape()==(1,3,size,size)
        assert info["actualOutputShape"][1]==4+len(engine.get_class_names())
        assert any(d.class_name=="person" and d.confidence>.35 for d in result)
        assert "torch" not in sys.modules and "ultralytics" not in sys.modules
    finally: engine.close()
