import asyncio
import json
import time
from dataclasses import replace

from websockets.asyncio.server import serve

from app.config import Settings, load_settings, validate_settings
from app.demo_protocol import DemoProtocol, encode_demo_frame, validate_demo_result
from app.inference_base import Detection
from app.pipeline import FramePipeline
from app.protocol import Frame, build_detection_message
from app.ws_client import YoloWorkerClient
from app import ROOT
from app.demo_gesture import DemoGestureStateMachine


class _Names:
    def get_class_names(self):
        return {0:"person",1:"finger_gun"}
    def get_model_info(self):
        return {"classes":self.get_class_names(),"modelVersion":"test-yolo11n"}


class _Manager:
    backend = "onnx_cpu"
    status = "ready"
    def __init__(self):
        self.engine = _Names()
        self.loaded = False
        self.load_count = 0
        self.detections = []
    def initialize(self):
        if not self.loaded:
            self.loaded = True
            self.load_count += 1
    def infer_frame(self, image):
        return list(self.detections)
    def shutdown(self):
        self.loaded = False


def _settings(**changes):
    return replace(Settings(),protocol="demo-v0.4",camera_id=1,camera_ids=(1,2),
                   model_version="test-yolo11n",imgsz=640,
                   gesture_conf=.6,gesture_cooldown=10,**changes)


def test_v04_config_parses_two_integer_cameras(monkeypatch,tmp_path):
    monkeypatch.setenv("YOLO_PROTOCOL","demo-v0.4")
    monkeypatch.setenv("CAMERA_ID","1")
    monkeypatch.setenv("CAMERA_IDS","1,2")
    settings=load_settings(tmp_path/"absent.env")
    assert settings.camera_ids==(1,2)
    assert validate_settings(settings).max_fps==3


def test_v04_one_model_independent_tracking_counts_and_events(sample):
    pipeline=FramePipeline(_settings())
    manager=_Manager(); pipeline.manager=manager
    now=time.time()
    identities={1:set(),2:set()}; events={1:[],2:[]}
    try:
        for step in range(5):
            for camera_id in (1,2):
                offset=0 if camera_id==1 else 250
                people=[Detection(0,"person",.95,(40+offset,30,220+offset,340))]
                if camera_id==2:
                    people.append(Detection(0,"person",.92,(400,40,600,350)))
                manager.detections=people+[Detection(1,"finger_gun",.9,(90+offset,90,130+offset,140))]
                stamp=now+step*.5+camera_id*.01
                frame=Frame(camera_id,step+1,int(stamp*1000),sample,session_id="worker",
                            source_session_id=f"camera-{camera_id}",width=640,height=360)
                result,*_=pipeline.process_frame(frame)
                assert result["cameraId"]==camera_id and result["frameId"]==step+1
                assert result["personCount"]==camera_id
                identities[camera_id].update(d["trackId"] for d in result["detections"]
                                             if d["className"]=="person" and d["trackId"] is not None)
                events[camera_id].extend(result["events"])
        assert manager.load_count==1
        assert identities[1] and identities[2] and identities[1].isdisjoint(identities[2])
        assert [e["eventType"] for e in events[1]]==["FINGER_GUN"]
        assert [e["eventType"] for e in events[2]]==["FINGER_GUN"]
        assert events[1][0]["trackId"] in identities[1]
        assert events[2][0]["trackId"] in identities[2]
        # Ten-second cooldown is independent by camera and prevents immediate duplicates.
        assert len(events[1])==len(events[2])==1
    finally:
        pipeline.close()


class _NetworkPipeline:
    def __init__(self):
        self.frames=[]; self.resets=[]
    def get_model_metadata(self):
        return {"classes":{0:"person",1:"finger_gun"},"modelVersion":"test-yolo11n"}
    def process_frame(self,frame):
        self.frames.append((frame.camera_id,frame.frame_id,frame.generation,frame.source_session_id))
        return build_detection_message(frame,[],"test-yolo11n",1,[],"test"),0,1,1
    def reset(self,camera_id=None):
        self.resets.append(camera_id)
    def expire_state(self,now):
        pass


def test_v04_alternating_mock_frames_and_independent_reconnect():
    async def run():
        done=asyncio.Event(); results=[]
        async def handler(ws):
            hello=json.loads(await ws.recv())
            assert hello["type"]=="hello" and hello["classes"]==["person","finger_gun"]
            stamp=int(time.time()*1000)
            frames=[Frame(1,10,stamp,b"jpeg",source_session_id="a",width=640,height=360),
                    Frame(2,20,stamp+1,b"jpeg",source_session_id="b",width=640,height=360),
                    # Camera 1 reconnects with a new session/lower frame ID while camera 2 continues.
                    Frame(1,1,stamp+2,b"jpeg",source_session_id="a2",width=640,height=360),
                    Frame(2,21,stamp+3,b"jpeg",source_session_id="b",width=640,height=360),
                    # Then camera 2 reconnects while camera 1 continues unaffected.
                    Frame(2,1,stamp+4,b"jpeg",source_session_id="b2",width=640,height=360),
                    Frame(1,2,stamp+5,b"jpeg",source_session_id="a2",width=640,height=360)]
            for frame in frames:
                await ws.send(encode_demo_frame(frame))
                results.append(json.loads(await asyncio.wait_for(ws.recv(),2)))
            done.set(); await ws.wait_closed()
        async with serve(handler,"127.0.0.1",0,compression=None) as server:
            port=server.sockets[0].getsockname()[1]
            engine=_NetworkPipeline()
            settings=_settings(ws_url=f"ws://127.0.0.1:{port}/ws/yolo/worker")
            client=YoloWorkerClient(settings,engine,DemoProtocol())
            task=asyncio.create_task(client.run_forever())
            try:
                await asyncio.wait_for(done.wait(),8)
                assert [(r["cameraId"],r["frameId"]) for r in results]==[(1,10),(2,20),(1,1),(2,21),(2,1),(1,2)]
                assert all(r["personCount"]==0 for r in results)
                assert engine.frames[0][2]==1 and engine.frames[2][2]==2
                assert engine.frames[1][2]==1 and engine.frames[3][2]==1
                assert engine.frames[4][2]==2 and engine.frames[5][2]==2
                assert 1 in engine.resets and 2 in engine.resets
                assert client.metrics.counts["received"]==6 and client.metrics.counts["sent"]==6
            finally:
                await client.stop(); await asyncio.wait_for(task,5)
    asyncio.run(run())


def test_v04_result_accepts_finger_gun_event():
    result={"type":"result","cameraId":2,"frameId":7,"capturedAt":1,"inferMs":2.5,
            "personCount":1,"detections":[{"cls":"person","conf":.9,"box":[.1,.1,.8,.9],"trackId":4},
            {"cls":"finger_gun","conf":.8,"box":[.2,.2,.3,.3],"trackId":4}],
            "events":[{"eventType":"FINGER_GUN","trackId":4,"confidence":.8,
                       "detectedAt":"2026-11-12T10:00:00.000+09:00"}]}
    validate_demo_result(result)


def test_v04_two_camera_frame_interval_does_not_reset_continuity():
    machine=DemoGestureStateMachine(["person","finger_gun"],gesture_class="finger_gun",max_gap=1.0)
    detections=[Detection(1,"finger_gun",.92,(10,10,20,20),track_id=7)]
    assert machine.process(1,detections,10.0,"model")==[]
    assert machine.process(1,detections,10.9,"model")==[]
    events=machine.process(1,detections,11.8,"model")
    assert len(events)==1 and events[0]["eventType"]=="FINGER_GUN"
    assert machine.get_diagnostics(1)["reason"]=="event_created"


def test_v04_real_onnx_alternating_websocket_pipeline(sample):
    if not (ROOT/"models/best.onnx").is_file():
        return
    async def run():
        done=asyncio.Event(); results=[]
        async def handler(ws):
            await ws.recv()
            stamp=int(time.time()*1000)
            for frame_id,camera_id in enumerate((1,2,1,2),1):
                await ws.send(encode_demo_frame(Frame(camera_id,frame_id,stamp+frame_id,sample,
                    source_session_id=f"real-{camera_id}",width=640,height=360)))
                results.append(json.loads(await asyncio.wait_for(ws.recv(),3)))
            done.set(); await ws.wait_closed()
        async with serve(handler,"127.0.0.1",0,compression=None) as server:
            port=server.sockets[0].getsockname()[1]
            settings=_settings(ws_url=f"ws://127.0.0.1:{port}/ws/yolo/worker",
                onnx_model_path=ROOT/"models/best.onnx",enable_gesture=False,max_fps=3)
            pipeline=FramePipeline(settings); pipeline.load_model()
            session_identity=id(pipeline.manager.engine.session)
            client=YoloWorkerClient(settings,pipeline,DemoProtocol())
            task=asyncio.create_task(client.run_forever())
            try:
                await asyncio.wait_for(done.wait(),8)
                assert [(r["cameraId"],r["frameId"]) for r in results]==[(1,1),(2,2),(1,3),(2,4)]
                assert all(r["type"]=="result" for r in results)
                assert id(pipeline.manager.engine.session)==session_identity
                assert pipeline.tracker.get_tracking_status()["cameras"]==2
            finally:
                await client.stop(); await asyncio.wait_for(task,5); pipeline.close()
    asyncio.run(run())
