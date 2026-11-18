from dataclasses import replace
from pathlib import Path
import json
import time

import pytest

from app.config import Settings
from app.demo_gesture import associate_person_tracks
from app.demo_protocol import DemoProtocol,validate_demo_result
from app.inference_base import Detection
from app.onnx_engine import OnnxInferenceEngine
from app.pipeline import FramePipeline
from app.protocol import Frame
from mock_server.frame_source import demo_jpeg


MODEL=Path(__file__).resolve().parents[1]/"models"/"best.onnx"


@pytest.fixture
def final_model():
    if not MODEL.is_file():
        pytest.skip("Final best.onnx not installed")
    return MODEL


@pytest.mark.real
def test_final_model_metadata_and_person_inference(final_model):
    engine=OnnxInferenceEngine(replace(Settings(),onnx_model_path=final_model,
                                        allow_demo_model=False,imgsz=640))
    try:
        engine.load_model()
        info=engine.get_model_info()
        assert info["inputShape"]==[1,3,640,640]
        assert info["actualOutputShape"]==[1,6,8400]
        assert info["layout"]=="raw_bcn" and info["nmsIncluded"] is False
        assert info["classes"]=={0:"person",1:"finger_gun"}
        from app.preprocessing import decode_jpeg
        detections=engine.infer(decode_jpeg(demo_jpeg()))
        assert any(d.class_name=="person" for d in detections)
    finally:
        engine.close()


@pytest.mark.real
def test_final_model_pipeline_hello_count_and_no_help_event(final_model):
    settings=replace(Settings(),protocol="demo-v0.3",camera_id=1,onnx_model_path=final_model,
        allow_demo_model=False,imgsz=640,model_version="icn-v1-yolo11n-finger-gun",
        worker_id="suam-school-pc",enable_gesture=False)
    pipeline=FramePipeline(settings)
    try:
        pipeline.load_model()
        hello=json.loads(DemoProtocol().registration(1,"unused",pipeline.get_model_metadata(),
                                                     settings.worker_id))
        assert hello=={"type":"hello","workerId":"suam-school-pc",
            "modelVersion":"icn-v1-yolo11n-finger-gun","classes":["person","finger_gun"]}
        jpeg=demo_jpeg(); stamp=int(time.time()*1000)
        result=None
        for frame_id in range(1,5):
            result,*_=pipeline.process_frame(Frame(1,frame_id,stamp+frame_id*350,jpeg,
                                                   session_id="final",width=640,height=360))
        wire=json.loads(DemoProtocol().serialize(result))
        validate_demo_result(wire)
        assert wire["personCount"]==sum(d["cls"]=="person" for d in wire["detections"])
        assert wire["events"]==[]
        assert any(d["cls"]=="person" and d["trackId"] is not None for d in wire["detections"])
    finally:
        pipeline.close()


def test_finger_gun_preserved_and_conservatively_associated():
    person=Detection(0,"person",.9,(0,0,100,200),17)
    finger=Detection(1,"finger_gun",.8,(30,40,50,70))
    linked=associate_person_tracks([person,finger])
    assert linked[1].class_name=="finger_gun" and linked[1].track_id==17
    second=Detection(0,"person",.8,(20,0,120,200),18)
    assert associate_person_tracks([person,second,finger])[-1].track_id is None
    wire={"type":"result","cameraId":1,"frameId":1,"capturedAt":1,"inferMs":1,
          "personCount":1,"detections":[
              {"cls":"person","conf":.9,"box":[0,0,1,1],"trackId":17},
              {"cls":"finger_gun","conf":.8,"box":[.3,.2,.5,.4],"trackId":17}],
          "events":[]}
    validate_demo_result(wire)
