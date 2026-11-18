"""Local one-camera v0.3 relay. No frame or detection persistence."""
import asyncio
import hmac
import ipaddress
import json
import os
import time
import uuid
from dataclasses import dataclass, field, replace
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from app.demo_protocol import encode_demo_frame, validate_demo_result, parse_camera_id_setting
from local_relay.android_protocol import camera_identity, parse_android_frame


@dataclass(frozen=True)
class RelaySettings:
    camera_id: int = 1
    worker_token: str = field(default="local-worker-demo",repr=False)
    camera_token: str = field(default="local-camera-demo",repr=False)
    max_age: float = 5.0
    idle_seconds: float = 3.0
    result_timeout: float = 2.0

    def __post_init__(self):
        import math
        from app.demo_protocol import validate_camera_id
        validate_camera_id(self.camera_id)
        if not self.worker_token or not self.camera_token:
            raise ValueError("Local test tokens must not be empty")
        if any(not math.isfinite(v) or v<=0 for v in (self.max_age,self.idle_seconds,self.result_timeout)):
            raise ValueError("Invalid timeout")


def loopback(host):
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class RelayState:
    def __init__(self,settings):
        self.settings = settings
        self.camera = self.worker = None
        self.camera_session = ""
        self.stream_active = False
        self.last_received = self.result_time = 0.0
        self.pending = self.inflight = self.result = None
        self.changed = asyncio.Event()
        self.stats = dict(received=0,forwarded=0,returned=0,dropped=0,rejected=0,staleResults=0,
                          errors=0,timeouts=0,cameraConnections=0,workerConnections=0)
        self.mode = None

    def transition(self,active):
        self.camera_session = str(uuid.uuid4())
        self.stream_active = active
        self.pending = self.inflight = self.result = None
        self.changed.set()

    def offer(self,frame,mode):
        if not self.stream_active:
            self.transition(True)
        if self.pending is not None:
            self.stats["dropped"] += 1
        self.pending = replace(frame,source_session_id=self.camera_session)
        self.last_received = time.monotonic()
        self.mode = mode
        self.stats["received"] += 1
        self.changed.set()

    def snapshot(self):
        active = self.stream_active and time.monotonic()-self.last_received<=self.settings.idle_seconds
        fresh = self.result is not None and time.monotonic()-self.result_time<=self.settings.max_age
        status = "OFFLINE" if not active else "LIVE" if fresh and self.worker else "STALE"
        return {"service":"local-android-yolo-relay","cameraId":self.settings.camera_id,
            "cameraConnected":self.camera is not None,"workerConnected":self.worker is not None,
            "status":status,"personCount":self.result["personCount"] if status=="LIVE" else None,
            "protocolMode":self.mode,"pendingFrames":int(self.pending is not None),
            "inflightFrames":int(self.inflight is not None),"counters":dict(self.stats)}


def create_app(settings=None):
    settings = settings or RelaySettings(camera_id=parse_camera_id_setting(os.getenv("RELAY_CAMERA_ID","1")),
        worker_token=os.getenv("YOLO_WORKER_TOKEN","local-worker-demo"),
        camera_token=os.getenv("YOLO_CAMERA_TOKEN","local-camera-demo"))
    state = RelayState(settings)
    app = FastAPI(title="Local YOLO DEMO v0.3 relay",docs_url=None,redoc_url=None,openapi_url=None)
    app.state.relay = state

    @app.get("/health")
    async def health():
        return {"status":"ok"}

    def require_local(request):
        if not request.client or not loopback(request.client.host):
            raise HTTPException(403,"Local inspection only")

    @app.get("/status")
    async def status(request: Request):
        require_local(request)
        return state.snapshot()

    @app.get("/result")
    async def result(request: Request):
        require_local(request)
        status = state.snapshot()["status"]
        return {"status":status,"result":state.result if status=="LIVE" else None}

    async def reject(ws,code):
        await ws.accept()
        await ws.close(code)

    @app.websocket("/ws/yolo/camera")
    async def camera(ws: WebSocket):
        if not hmac.compare_digest(ws.query_params.get("token","").encode(),settings.camera_token.encode()):
            return await reject(ws,4401)
        try:
            camera_identity(ws.headers.get("x-camera-id"),ws.query_params.get("cameraId"),settings.camera_id)
            if parse_camera_id_setting(ws.query_params.get("camera_id",str(settings.camera_id)))!=settings.camera_id:
                raise ValueError("Legacy query mismatch")
        except ValueError:
            return await reject(ws,4404)
        old = state.camera
        state.camera = ws
        state.transition(True)
        state.last_received = time.monotonic()
        state.stats["cameraConnections"] += 1
        last_id,last_stamp,sequence,last_accept = -1,-1,0,0.0
        mode_selected = None
        try:
            await ws.accept()
            if old:
                await old.close(4409)
            await ws.send_json({"type":"hello","cameraId":settings.camera_id,"maxFps":10})
            while state.camera is ws:
                message = await ws.receive()
                if state.camera is not ws:
                    break
                if message["type"]=="websocket.disconnect":
                    break
                try:
                    sequence += 1
                    frame,mode = parse_android_frame(message.get("bytes"),settings.camera_id,sequence,
                                                    max(int(time.time()*1000),last_stamp+1))
                    if mode_selected is not None and mode!=mode_selected:
                        raise ValueError("Mode changed within camera connection")
                    mode_selected = mode
                    age = time.time()-frame.timestamp_ms/1000
                    if frame.frame_id<=last_id or frame.timestamp_ms<=last_stamp or age>settings.max_age or age < -5:
                        raise ValueError("Stale or unordered frame")
                    last_id,last_stamp = frame.frame_id,frame.timestamp_ms
                    # Legacy Android's long counter does not reset on reconnect. Translate
                    # to a local virtual camera sequence; native v0.3 IDs stay untouched.
                    if mode!="demo-v0.3":
                        frame = replace(frame,frame_id=sequence)
                    if time.monotonic()-last_accept<.1:
                        state.stats["dropped"] += 1
                        continue
                    last_accept = time.monotonic()
                    state.offer(frame,mode)
                except (ValueError,TypeError):
                    state.stats["rejected"] += 1
        except (WebSocketDisconnect,RuntimeError):
            pass
        finally:
            if state.camera is ws:
                state.camera = None
                state.transition(False)

    @app.websocket("/ws/yolo/worker")
    async def worker(ws: WebSocket):
        if not ws.client or not loopback(ws.client.host):
            return await reject(ws,4401)
        if not hmac.compare_digest(ws.query_params.get("token","").encode(),settings.worker_token.encode()):
            return await reject(ws,4401)
        tasks = []
        try:
            await ws.accept()
            hello = json.loads(await asyncio.wait_for(ws.receive_text(),10))
            if (not isinstance(hello,dict) or hello.get("type")!="hello"
                or not isinstance(hello.get("workerId"),str) or not 1<=len(hello["workerId"])<=128
                or not isinstance(hello.get("modelVersion"),str) or not 1<=len(hello["modelVersion"])<=128
                or not isinstance(hello.get("classes"),list) or "person" not in hello["classes"]
                or any(c not in {"person","head","help_gesture","finger_gun"} for c in hello["classes"])):
                raise ValueError("Invalid worker hello")
            old = state.worker
            state.worker = ws
            state.inflight = state.result = None
            state.stats["workerConnections"] += 1
            if old:
                await old.close(4409)

            async def send_frames():
                next_send = 0.0
                while state.worker is ws:
                    state.changed.clear()
                    now = time.monotonic()
                    if state.stream_active and now-state.last_received>settings.idle_seconds:
                        state.transition(False)
                    if state.inflight and now-state.inflight[1]>=settings.result_timeout:
                        state.inflight = None
                        state.stats["timeouts"] += 1
                    if state.pending and state.inflight is None and now>=next_send:
                        frame,state.pending = state.pending,None
                        if time.time()-frame.timestamp_ms/1000>settings.max_age:
                            state.stats["dropped"] += 1
                        else:
                            state.inflight = (frame,now)
                            next_send = now+1/3
                            await asyncio.wait_for(ws.send_bytes(encode_demo_frame(frame)),2)
                            state.stats["forwarded"] += 1
                    try:
                        await asyncio.wait_for(state.changed.wait(),.025)
                    except TimeoutError:
                        pass

            async def receive_results():
                while state.worker is ws:
                    raw = await ws.receive_text()
                    if len(raw)>1024*1024:
                        raise ValueError("Result too large")
                    message = json.loads(raw)
                    if not isinstance(message,dict):
                        raise ValueError("Invalid result")
                    is_error = message.get("type")=="error"
                    if is_error:
                        if (type(message.get("frameId")) is not int or message.get("code") not in {"BAD_FRAME","MODEL_ERROR"}
                            or not isinstance(message.get("message"),str) or len(message["message"])>256):
                            raise ValueError("Invalid error")
                    else:
                        validate_demo_result(message)
                    expected = state.inflight[0] if state.inflight else None
                    if (state.worker is not ws or not expected or not state.stream_active
                        or expected.source_session_id!=state.camera_session or message["frameId"]!=expected.frame_id
                        or (not is_error and (message["cameraId"]!=settings.camera_id
                            or message["capturedAt"]!=expected.timestamp_ms
                            or message.get("cameraSessionId",state.camera_session)!=state.camera_session))):
                        state.stats["staleResults"] += 1
                        continue
                    state.inflight = None
                    state.changed.set()
                    if is_error:
                        state.stats["errors"] += 1
                    elif time.time()-expected.timestamp_ms/1000>settings.max_age:
                        state.stats["staleResults"] += 1
                    else:
                        state.result = message
                        state.result_time = time.monotonic()
                        state.stats["returned"] += 1

            tasks = [asyncio.create_task(send_frames()),asyncio.create_task(receive_results())]
            done,_ = await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        except (WebSocketDisconnect,RuntimeError):
            pass
        except (ValueError,TypeError,KeyError,TimeoutError):
            state.stats["rejected"] += 1
            try:
                await ws.close(1008,"Invalid worker protocol")
            except (RuntimeError,WebSocketDisconnect):
                pass
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
            if state.worker is ws:
                state.worker = None
                state.inflight = state.result = None
    return app


app = create_app()
