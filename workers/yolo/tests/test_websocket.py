import asyncio
import json
import socket
import time
from dataclasses import replace
import pytest
from websockets.asyncio.server import serve
from app.config import Settings
from app.protocol import Frame,encode_frame,build_detection_message
from app.ws_client import YoloWorkerClient,AuthenticationError,classify_http_status,classify_close_code
from mock_server.server import MockServer


class FakePipeline:
    """Network tests deliberately use no model; real test is separate."""
    def __init__(self,delay=0): self.delay=delay; self.resets=0; self.contexts=[]
    def process_frame(self,frame):
        time.sleep(self.delay)
        self.contexts.append((frame.session_id,frame.generation))
        return build_detection_message(frame,[],"fake",1),0,1,1
    def reset(self): self.resets+=1


async def with_client(handler,body,engine=None,**changes):
    async with serve(handler,"127.0.0.1",0,compression=None) as server:
        port=server.sockets[0].getsockname()[1]
        client=YoloWorkerClient(replace(Settings(),ws_url=f"ws://127.0.0.1:{port}/ws/yolo/worker",**changes),engine or FakePipeline())
        task=asyncio.create_task(client.run_forever())
        try: await body(client,task)
        finally:
            await client.stop()
            if not task.done(): await asyncio.wait_for(task,5)


async def register(ws):
    r=json.loads(await ws.recv())
    await ws.send(json.dumps({"type":"registered","protocol":"mock-v1"}))
    return r


def test_mock_reconnect_and_shutdown():
    async def run():
        mock=MockServer(b"jpeg",frames=3,fps=30,disconnect_after=2)
        async def body(client,task):
            await asyncio.wait_for(mock.done.wait(),10)
            assert mock.connections==2 and not mock.errors and len(mock.sessions)==2
            assert client.metrics.counts["sent"]>0
        await with_client(mock.handler,body,max_fps=100)
    asyncio.run(run())


def test_auth_rejection_is_terminal():
    async def run():
        mock=MockServer(b"jpeg",token="required")
        async def body(client,task):
            with pytest.raises(AuthenticationError): await asyncio.wait_for(task,5)
            assert mock.connections==0
        await with_client(mock.handler,body,token="wrong")
    asyncio.run(run())


def test_valid_authentication():
    async def run():
        mock=MockServer(b"jpeg",frames=2,fps=30,token="local-test-only")
        async def body(client,task):
            await asyncio.wait_for(mock.done.wait(),5)
            assert not mock.errors and mock.connections==1
        await with_client(mock.handler,body,token="local-test-only",max_fps=100)
    asyncio.run(run())


def test_remote_error_guidance_is_specific():
    assert classify_close_code(4401)==(True,"WebSocket 4401: YOLO_WORKER_TOKEN is missing or invalid")
    assert "camera registration" in classify_close_code(4404)[1]
    assert "another Worker" in classify_close_code(4409)[1]
    assert classify_http_status(404)[0] and "/ws/yolo/worker" in classify_http_status(404)[1]
    assert not classify_http_status(502)[0] and "upstream" in classify_http_status(502)[1]


def test_refused_connection_retries_and_stop():
    async def run():
        sock=socket.socket(); sock.bind(("127.0.0.1",0)); port=sock.getsockname()[1]; sock.close()
        client=YoloWorkerClient(replace(Settings(),ws_url=f"ws://127.0.0.1:{port}/ws/yolo/worker"),FakePipeline())
        task=asyncio.create_task(client.run_forever())
        await asyncio.sleep(.15)
        assert not task.done() and not client.metrics.connected
        await client.stop(); await asyncio.wait_for(task,3)
    asyncio.run(run())


def test_bad_frames_and_latest_only_under_slow_inference():
    async def run():
        done=asyncio.Event(); results=[]
        async def handler(ws):
            await register(ws)
            await ws.send(b"bad")
            await ws.send(encode_frame(Frame("wrong",1,int(time.time()*1000),b"x")))
            await ws.send(encode_frame(Frame("DEMO_T1_3",0,int((time.time()-20)*1000),b"x")))
            stamp=int(time.time()*1000)
            for i in range(30):
                await ws.send(encode_frame(Frame("DEMO_T1_3",i,stamp+i,b"jpeg")))
                await asyncio.sleep(.002)
            while True:
                result=json.loads(await ws.recv()); results.append(result)
                if result["frameId"]==29: break
            done.set(); await ws.wait_closed()
        async def body(client,task):
            await asyncio.wait_for(done.wait(),5)
            assert client.buffer.dropped>10 and len(client.buffer.frames)<=1
            assert client.metrics.counts["received"]==30
            assert client.metrics.counts["invalid"]==1 and client.metrics.counts["stale"]>=1
            assert len(results)<30
        await with_client(handler,body,FakePipeline(.15),max_fps=100)
    asyncio.run(run())


def test_session_change_discards_inflight_and_offline_count_unknown():
    async def run():
        done=asyncio.Event(); results=[]
        async def handler(ws):
            await register(ws)
            await ws.send(encode_frame(Frame("DEMO_T1_3",99,int(time.time()*1000),b"x")))
            await asyncio.sleep(.04)
            await ws.send(json.dumps({"type":"camera_session","cameraId":"DEMO_T1_3","sessionId":"new"}))
            await ws.send(encode_frame(Frame("DEMO_T1_3",0,int(time.time()*1000),b"x")))
            result=json.loads(await ws.recv()); results.append(result)
            assert result["frameId"]==0
            await ws.send(json.dumps({"type":"camera_offline","cameraId":"DEMO_T1_3"}))
            status=json.loads(await ws.recv())
            assert status["status"]=="OFFLINE" and status["personCount"] is None
            done.set(); await ws.wait_closed()
        async def body(client,task):
            await asyncio.wait_for(done.wait(),5)
            assert client.metrics.counts["stale"]>=1 and len(results)==1
        await with_client(handler,body,FakePipeline(.15),max_fps=100)
    asyncio.run(run())


def test_idle_stale_then_offline_and_duplicate_rejection():
    async def run():
        done=asyncio.Event()
        async def handler(ws):
            await register(ws)
            stamp=int(time.time()*1000)
            packet=encode_frame(Frame("DEMO_T1_3",5,stamp,b"x"))
            await ws.send(packet)
            first=json.loads(await ws.recv())
            assert first["type"]=="detection"
            await ws.send(packet)
            await ws.send(encode_frame(Frame("DEMO_T1_3",4,stamp+1,b"x")))
            statuses=[json.loads(await ws.recv()),json.loads(await ws.recv())]
            assert [s["status"] for s in statuses]==["STALE","OFFLINE"]
            assert all(s["personCount"] is None for s in statuses)
            done.set(); await ws.wait_closed()
        async def body(client,task):
            await asyncio.wait_for(done.wait(),5)
            assert client.metrics.counts["rejected"]==2
        await with_client(handler,body,max_frame_age=.1,offline_seconds=1.5)
    asyncio.run(run())


@pytest.mark.real
def test_real_onnx_websocket_pipeline(real_model,sample):
    async def run():
        from app.pipeline import FramePipeline
        pipeline=FramePipeline(Settings())
        pipeline.load_model()
        mock=MockServer(sample,frames=4,disconnect_after=3,fps=10)
        async def body(client,task):
            await asyncio.wait_for(mock.done.wait(),15)
            assert not mock.errors and mock.connections==2
            assert all(r["personCount"]>=1 and r["eventCount"]==0 for r in mock.results)
            assert sum(r["trackedPersons"]>0 for r in mock.results)>=2
        try: await with_client(mock.handler,body,pipeline,max_fps=30)
        finally: pipeline.close()
    asyncio.run(run())
