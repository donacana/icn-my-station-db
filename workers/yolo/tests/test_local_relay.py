import asyncio
import json
import socket
import time
from contextlib import asynccontextmanager
from dataclasses import replace
import pytest
pytest.importorskip("fastapi",reason="Install requirements-relay.txt for local adapter tests")
pytest.importorskip("uvicorn",reason="Install requirements-relay.txt for local adapter tests")
import uvicorn
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed
from app.config import Settings
from app import ROOT
from app.demo_protocol import DemoProtocol,parse_demo_frame,encode_demo_frame,validate_demo_result
from app.demo_gesture import DemoGestureStateMachine,associate_person_tracks
from app.inference_base import Detection
from app.pipeline import FramePipeline
from app.ws_client import YoloWorkerClient
from local_relay.android_protocol import parse_android_frame
from local_relay.server import RelaySettings,create_app
from tools.android_simulator import camera_packet,CAMERA_ID


class FakePipeline:
    def __init__(self): self.resets=0
    def get_model_metadata(self):
        return {"modelVersion":"fake","classes":{0:"person"}}
    def process_frame(self,frame):
        from app.protocol import build_detection_message
        return build_detection_message(frame,[],"fake",1),0,1,1
    def reset(self): self.resets+=1


@asynccontextmanager
async def relay(**changes):
    sock=socket.socket(); sock.bind(("127.0.0.1",0)); sock.listen(128); sock.setblocking(False)
    port=sock.getsockname()[1]
    app=create_app(RelaySettings(**changes))
    server=uvicorn.Server(uvicorn.Config(app,log_level="critical",access_log=False,proxy_headers=False,ws_per_message_deflate=False))
    task=asyncio.create_task(server.serve(sockets=[sock]))
    try:
        async with asyncio.timeout(5):
            while not server.started: await asyncio.sleep(.01)
        yield f"ws://127.0.0.1:{port}",app.state.relay
    finally:
        server.should_exit=True
        await asyncio.wait_for(task,5)
        sock.close()


def camera_url(base,token="local-camera-demo",camera=CAMERA_ID):
    return f"{base}/ws/yolo/camera?cameraId={camera}&token={token}"


async def worker_socket(base):
    ws=await connect(base+"/ws/yolo/worker?token=local-worker-demo",proxy=None)
    await ws.send(json.dumps(dict(type="hello",workerId="test",modelVersion="test",classes=["person"])))
    return ws


def fake_result(frame):
    return dict(type="result",cameraId=frame.camera_id,frameId=frame.frame_id,capturedAt=frame.timestamp_ms,
                inferMs=1,personCount=0,detections=[],events=[],cameraSessionId=frame.source_session_id)


@pytest.mark.parametrize("mode",["ICN1","RAW_JPEG","demo-v0.3"])
def test_android_packets(sample,mode):
    packet=camera_packet(sample,1,mode)
    frame,actual=parse_android_frame(packet,CAMERA_ID,1)
    assert actual==mode and (frame.width,frame.height)==(640,360)
    assert parse_demo_frame(encode_demo_frame(frame)).jpeg==sample
    with pytest.raises(ValueError): parse_android_frame(packet[:-12],CAMERA_ID,1)


@pytest.mark.parametrize("value",[0,-1,2**32,True])
def test_demo_uint32(sample,value):
    frame,_=parse_android_frame(camera_packet(sample,1),CAMERA_ID,1)
    with pytest.raises(ValueError): encode_demo_frame(replace(frame,frame_id=value))


def test_demo_bad_header():
    for packet in [b"",b"\xff"*20,b"\0\0\0\x02{}jpeg",b"\0\0\0\x02\xff\xffjpeg"]:
        with pytest.raises(ValueError): parse_demo_frame(packet)


def test_gesture_continuity_cooldown_and_association():
    person=Detection(0,"person",.9,(0,0,100,200),7)
    hand=Detection(2,"help_gesture",.85,(40,60,60,80))
    head=Detection(1,"head",.9,(40,10,60,30))
    ds=associate_person_tracks([person,hand,head])
    assert [d.track_id for d in ds]==[7,7,7]
    sm=DemoGestureStateMachine(["person","help_gesture"])
    for t in [100,100.5,101]: assert not sm.process("c",ds,t,"m")
    event=sm.process("c",ds,101.5,"m")
    assert event[0]["eventType"]=="HELP_GESTURE" and event[0]["detectedAt"].endswith("+09:00")
    for n in range(1,20): assert not sm.process("c",ds,101.5+n*.5,"m")
    assert sm.process("c",ds,111.5,"m")
    assert not sm.process("c",ds,110,"m")
    assert not sm.process("c",ds,112,"m",True)
    ambiguous=associate_person_tracks([person,replace(person,track_id=8),hand])
    assert ambiguous[-1].track_id is None
    assert not DemoGestureStateMachine(["person"]).enabled
    sm.reset_state()
    assert not sm.process("c",ds,200,"m")
    assert not sm.process("c",[],200.5,"m")
    assert not sm.process("c",ds,201.5,"m")
    assert not sm.process("c",ds,203,"m")


def test_auth_and_replacement(sample):
    async def run():
        async with relay() as (base,state):
            for url,code in [(camera_url(base,"wrong"),4401),(camera_url(base,camera="unknown"),4404),
                             (base+"/ws/yolo/worker?token=wrong",4401)]:
                async with connect(url,proxy=None) as ws:
                    with pytest.raises(ConnectionClosed) as e: await ws.recv()
                    assert e.value.rcvd.code==code
            async with connect(camera_url(base),proxy=None) as c1:
                assert json.loads(await c1.recv())["maxFps"]==10
                async with connect(camera_url(base),proxy=None) as c2:
                    await c2.recv()
                    with pytest.raises(ConnectionClosed) as e: await c1.recv()
                    assert e.value.rcvd.code==4409
            w1=await worker_socket(base)
            w2=await worker_socket(base)
            try:
                with pytest.raises(ConnectionClosed) as e: await w1.recv()
                assert e.value.rcvd.code==4409
            finally: await w1.close(); await w2.close()
    asyncio.run(run())


def test_latest_timeout_rate_and_stale_results(sample):
    async def run():
        async with relay(result_timeout=.5) as (base,state):
            w=await worker_socket(base)
            try:
                async with connect(camera_url(base),proxy=None) as c:
                    await c.recv()
                    await c.send(camera_packet(sample,1,"demo-v0.3"))
                    first=parse_demo_frame(await asyncio.wait_for(w.recv(),2))
                    start=time.monotonic()
                    for i in range(2,5):
                        await asyncio.sleep(.11)
                        await c.send(camera_packet(sample,i,"demo-v0.3"))
                    second=parse_demo_frame(await asyncio.wait_for(w.recv(),2))
                    assert second.frame_id==4 and time.monotonic()-start>=.45
                    assert state.stats["timeouts"]==1 and state.stats["dropped"]>=1
                    await w.send(json.dumps(fake_result(first)))
                    await w.send(json.dumps(fake_result(second)))
                    await asyncio.sleep(.05)
                    assert state.stats["staleResults"]==1 and state.stats["returned"]==1
                    await c.send(camera_packet(sample,5,"demo-v0.3"))
                    third=parse_demo_frame(await asyncio.wait_for(w.recv(),2))
                    assert third.frame_id==5
                    await w.send(json.dumps(dict(type="error",frameId=5,code="BAD_FRAME",message="decode failed")))
                    await asyncio.sleep(.05)
                    assert state.stats["errors"]==1
                async with asyncio.timeout(2):
                    while state.camera is not None: await asyncio.sleep(.01)
                assert state.snapshot()["personCount"] is None
            finally: await w.close()
    asyncio.run(run())


@pytest.mark.parametrize("mode",["ICN1","RAW_JPEG","demo-v0.3"])
@pytest.mark.real
def test_real_onnx_relay_and_reconnect(real_model,sample,mode):
    async def run():
        async with relay() as (base,state):
            settings=replace(Settings(),ws_url=base+"/ws/yolo/worker",protocol="demo-v0.3",camera_id=CAMERA_ID,token="local-worker-demo")
            pipeline=FramePipeline(settings)
            pipeline.load_model()
            client=YoloWorkerClient(settings,pipeline)
            task=asyncio.create_task(client.run_forever())
            try:
                async with asyncio.timeout(15):
                    while state.stats["workerConnections"]<1: await asyncio.sleep(.02)
                    for session in range(2):
                        async with connect(camera_url(base),additional_headers={"X-Camera-ID":str(CAMERA_ID)},proxy=None) as c:
                            await c.recv()
                            for i in range(1,5):
                                before=state.stats["returned"]
                                await c.send(camera_packet(sample,i,mode))
                                while state.stats["returned"]==before:
                                    if task.done(): task.result()
                                    await asyncio.sleep(.02)
                                result=state.result
                                validate_demo_result(result)
                                assert result["personCount"]>=1 and result["events"]==[]
                                if i>=3: assert any(d["trackId"] is not None for d in result["detections"])
                                await asyncio.sleep(.12)
                        if session==0:
                            await state.worker.close(1012)
                            while state.stats["workerConnections"]<2: await asyncio.sleep(.02)
                    assert state.stats["returned"]==8 and state.stats["cameraConnections"]==2
            finally:
                await client.stop()
                await asyncio.wait_for(task,5)
                pipeline.close()
    asyncio.run(run())


def test_worker_bad_jpeg_error_and_recovery(real_model,sample):
    from websockets.asyncio.server import serve
    from app.protocol import Frame
    async def run():
        done=asyncio.Event()
        received=[]
        async def handler(ws):
            hello=json.loads(await ws.recv())
            assert hello["type"]=="hello" and hello["classes"]==["person"]
            for i,jpeg in enumerate((b"bad jpeg",sample),1):
                frame=Frame(CAMERA_ID,i,int(time.time()*1000),jpeg,width=640,height=360)
                await ws.send(encode_demo_frame(frame))
                received.append(json.loads(await ws.recv()))
                await asyncio.sleep(.1)
            done.set()
            await ws.wait_closed()
        async with serve(handler,"127.0.0.1",0) as server:
            port=server.sockets[0].getsockname()[1]
            settings=replace(Settings(),protocol="demo-v0.3",camera_id=CAMERA_ID,
                             onnx_model_path=ROOT/"models/yolo11n.onnx",
                             ws_url=f"ws://127.0.0.1:{port}/ws/yolo/worker")
            pipeline=FramePipeline(settings); pipeline.load_model()
            client=YoloWorkerClient(settings,pipeline)
            task=asyncio.create_task(client.run_forever())
            try:
                await asyncio.wait_for(done.wait(),8)
                assert received[0]==dict(type="error",frameId=1,code="BAD_FRAME",message="decode failed")
                assert received[1]["type"]=="result" and received[1]["personCount"]>=1
            finally:
                await client.stop(); await asyncio.wait_for(task,5); pipeline.close()
    asyncio.run(run())


def test_v03_hello_uses_configured_yolo11n_version(real_model):
    settings=replace(Settings(),protocol="demo-v0.3",camera_id=1,
                     onnx_model_path=ROOT/"models/yolo11n.onnx",
                     model_version="icn-v1-yolo11n",worker_id="suam-school-pc")
    pipeline=FramePipeline(settings)
    try:
        pipeline.load_model()
        message=json.loads(DemoProtocol().registration(1,"ignored",pipeline.get_model_metadata(),
                                                       settings.worker_id))
        assert message=={"type":"hello","workerId":"suam-school-pc",
                         "modelVersion":"icn-v1-yolo11n","classes":["person"]}
    finally:
        pipeline.close()


def test_v03_lower_frame_id_starts_new_camera_session():
    from websockets.asyncio.server import serve
    from app.protocol import Frame
    async def run():
        generations=[]
        done=asyncio.Event()
        class Engine(FakePipeline):
            def process_frame(self,frame):
                generations.append(frame.generation)
                return super().process_frame(frame)
        async def handler(ws):
            await ws.recv()
            stamp=int(time.time()*1000)
            for index,frame_id in enumerate((9,2),1):
                await ws.send(encode_demo_frame(Frame(1,frame_id,stamp+index,b"jpeg",
                                                      width=640,height=360)))
                await asyncio.sleep(.4)
            async with asyncio.timeout(3):
                while len(generations)<2:
                    await ws.recv()
            done.set()
            await ws.wait_closed()
        async with serve(handler,"127.0.0.1",0) as server:
            port=server.sockets[0].getsockname()[1]
            settings=replace(Settings(),protocol="demo-v0.3",camera_id=1,max_fps=3,
                             ws_url=f"ws://127.0.0.1:{port}/ws/yolo/worker")
            client=YoloWorkerClient(settings,Engine())
            task=asyncio.create_task(client.run_forever())
            try:
                await asyncio.wait_for(done.wait(),5)
                assert generations==[0,1]
            finally:
                await client.stop(); await asyncio.wait_for(task,5)
    asyncio.run(run())


@pytest.mark.parametrize("bad", ["1", "cam-t1-hall3", True, 1.0, 0, -1, 2**63, None])
def test_v03_reject_non_integer_camera_id(sample,bad):
    from app.protocol import Frame
    from app.config import validate_settings
    with pytest.raises(ValueError):
        encode_demo_frame(Frame(bad,1,1,sample,width=640,height=360))
    with pytest.raises(ValueError):
        validate_demo_result(dict(type="result",cameraId=bad,frameId=1,capturedAt=1,
                                 inferMs=1,personCount=0,detections=[],events=[]))
    with pytest.raises(ValueError):
        validate_settings(replace(Settings(),protocol="demo-v0.3",camera_id=bad))


def test_v03_config_and_bigint(monkeypatch,tmp_path,sample):
    from app.config import load_settings
    from app.protocol import Frame
    monkeypatch.setenv("YOLO_PROTOCOL","demo-v0.3")
    monkeypatch.setenv("CAMERA_ID","9223372036854775807")
    settings=load_settings(tmp_path/"absent.env")
    assert type(settings.camera_id) is int and settings.camera_id==2**63-1
    frame=Frame(settings.camera_id,1,1,sample,width=640,height=360)
    assert parse_demo_frame(encode_demo_frame(frame)).camera_id==2**63-1
    monkeypatch.setenv("CAMERA_ID","cam-t1-hall3")
    with pytest.raises(ValueError): load_settings(tmp_path/"absent.env")
