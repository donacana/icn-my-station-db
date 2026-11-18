"""Outbound loopback Mock WebSocket client with serialized inference thread."""
import asyncio
import logging
import random
import time
import uuid
from collections import defaultdict
from dataclasses import replace

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

from app.config import Settings, validate_settings
from app.frame_buffer import LatestFrameBuffer
from app.metrics import Metrics
from app.protocol import MAX_PACKET, MockProtocol, validate_frame_metadata

log = logging.getLogger(__name__)


class AuthenticationError(RuntimeError):
    pass


def classify_http_status(status: int) -> tuple[bool,str]:
    messages = {
        401:"HTTP 401: worker token authentication failed",
        403:"HTTP 403: worker access forbidden",
        404:"HTTP 404: /ws/yolo/worker is not deployed or the public proxy path is wrong",
        502:"HTTP 502: Nginx/gateway cannot reach the FastAPI upstream",
    }
    return status in {401,403,404}, messages.get(status,f"HTTP {status}: WebSocket upgrade rejected")


def classify_close_code(code: int | None) -> tuple[bool,str]:
    messages = {
        4401:"WebSocket 4401: YOLO_WORKER_TOKEN is missing or invalid",
        4404:"WebSocket 4404: configured camera registration was not found",
        4409:"WebSocket 4409: another Worker replaced this connection or replacement was rejected",
        4403:"WebSocket 4403: worker access forbidden",
        1008:"WebSocket 1008: server policy/contract rejected the Worker",
    }
    return code in messages, messages.get(code,f"WebSocket closed (code {code})")


class YoloWorkerClient:
    def __init__(self, settings: Settings, engine, protocol=None):
        self.settings = validate_settings(settings)
        self.engine = engine
        from app.demo_protocol import DemoProtocol
        self.protocol = protocol or (DemoProtocol() if settings.protocol in {"demo-v0.3", "demo-v0.4"} else MockProtocol())
        self.camera_ids = tuple(settings.camera_ids or (settings.camera_id,))
        self.buffer = LatestFrameBuffer(max_cameras=len(self.camera_ids))
        self.metrics = Metrics()
        self.stop_event = asyncio.Event()
        self.ws = None
        self.session_id = ""
        self.camera_states = {}
        self.camera_metrics = {camera_id:defaultdict(int) for camera_id in self.camera_ids}
        self._initialize_camera_states()

    def _initialize_camera_states(self):
        self.camera_states = {camera_id:{"generation":0,"last_frame_id":-1,"last_timestamp":-1,
            "last_received":0.0,"offline":False,"data_status":"OFFLINE","camera_session":None}
            for camera_id in self.camera_ids}

    async def connect(self):
        """Never log URL, headers, payloads or raw remote exceptions."""
        headers = {"Authorization": f"Bearer {self.settings.token}"} if self.settings.token else None
        url = self.settings.ws_url
        if hasattr(self.protocol,"connection_url"):
            url = self.protocol.connection_url(url,self.settings.token)
            headers = None
        from app.demo_protocol import MAX_DEMO_PACKET
        return await connect(url, additional_headers=headers,
                             max_size=max(MAX_PACKET,MAX_DEMO_PACKET), max_queue=1, ping_interval=20,
                             ping_timeout=20, open_timeout=10, close_timeout=3,
                             compression=None, proxy=None)

    async def register_worker(self) -> None:
        info = self.engine.get_model_metadata() if hasattr(self.engine,"get_model_metadata") else {}
        await self.ws.send(self.protocol.registration(self.settings.camera_id, self.session_id,
                           model_info=info,worker_id=self.settings.worker_id))
        names=info.get("classes",{})
        classes=list(names.values()) if isinstance(names,dict) else list(names)
        log.info("Worker hello sent: workerId=%s modelVersion=%s classes=%s cameras=%s",
                 self.settings.worker_id,info.get("modelVersion","unknown"),classes,self.camera_ids)
        if getattr(self.protocol,"expects_ack",True):
            self.protocol.check_ack(await asyncio.wait_for(self.ws.recv(), timeout=10))

    def invalidate_camera(self, camera_id) -> None:
        state = self.camera_states[camera_id]
        state["generation"] += 1
        state["last_frame_id"] = -1
        state["last_timestamp"] = -1
        self.buffer.clear(camera_id)
        state["offline"] = True
        if hasattr(self.engine,"reset"):
            try:
                self.engine.reset(camera_id)
            except TypeError:  # compatibility with legacy/mock engines
                self.engine.reset()

    async def receive_frames(self) -> None:
        async for message in self.ws:
            try:
                if isinstance(message, str):
                    control = self.protocol.control(message)
                    camera_id = control["cameraId"]
                    if camera_id in self.camera_states:
                        state = self.camera_states[camera_id]
                        if control["type"] == "camera_offline":
                            self.invalidate_camera(camera_id)
                            state["data_status"] = "OFFLINE"
                            await self.send_status(camera_id,"OFFLINE")
                        elif control["sessionId"] != state["camera_session"]:
                            self.invalidate_camera(camera_id)
                            state["camera_session"] = control["sessionId"]
                    continue
                frame = self.protocol.parse(message, self.session_id)
                validate_frame_metadata(frame)
                if frame.camera_id not in self.camera_states:
                    self.metrics.counts["rejected"] += 1
                    continue
                state = self.camera_states[frame.camera_id]
                if frame.source_session_id and frame.source_session_id != state["camera_session"]:
                    self.invalidate_camera(frame.camera_id)
                    state["camera_session"] = frame.source_session_id
                elif (self.settings.protocol in {"demo-v0.3", "demo-v0.4"} and not frame.source_session_id
                      and frame.frame_id < state["last_frame_id"] and frame.timestamp_ms > state["last_timestamp"]):
                    self.invalidate_camera(frame.camera_id)
                now = time.monotonic()
                if state["last_received"] and now - state["last_received"] > self.settings.offline_seconds and not state["offline"]:
                    self.invalidate_camera(frame.camera_id)
                if frame.frame_id <= state["last_frame_id"] or frame.timestamp_ms <= state["last_timestamp"]:
                    self.metrics.counts["rejected"] += 1
                    continue
                age = time.time() - frame.timestamp_ms / 1000
                if age > self.settings.max_frame_age or age < -5:
                    self.metrics.counts["stale"] += 1
                    continue
                state["last_frame_id"] = frame.frame_id
                state["last_timestamp"] = frame.timestamp_ms
                state["last_received"] = now
                state["offline"] = False
                state["data_status"] = "LIVE"
                self.metrics.counts["received"] += 1
                self.camera_metrics[frame.camera_id]["received"] += 1
                self.buffer.put_latest(replace(frame, generation=state["generation"]))
            except (ValueError, TypeError, KeyError):
                self.metrics.counts["invalid"] += 1
                log.warning("Rejected malformed frame message")

    def process_frame(self, frame):
        return self.engine.process_frame(frame)

    def current(self, frame) -> bool:
        state = self.camera_states.get(frame.camera_id)
        return (state is not None and frame.session_id == self.session_id and frame.generation == state["generation"]
                and time.monotonic() - frame.received_at <= self.settings.max_frame_age
                and time.time() - frame.timestamp_ms / 1000 <= self.settings.max_frame_age)

    async def send_status(self, camera_id, status):
        message = self.protocol.status(camera_id,status)
        if message is not None:
            await self.ws.send(message)

    async def send_detection_result(self, result: dict) -> None:
        await self.ws.send(self.protocol.serialize(result))
        self.metrics.counts["sent"] += 1
        self.camera_metrics[result["cameraId"]]["sent"] += 1
        if self.settings.log_result_summary:
            safe_detections=[{"cls":d["className"],"conf":round(d["confidence"],4),"trackId":d["trackId"]}
                             for d in result["detections"]]
            safe_events=[{"eventType":e.get("eventType"),"trackId":e.get("trackId"),
                          "confidence":round(e.get("confidence",0),4)} for e in result["events"]]
            log.info("Result sent cameraId=%s frameId=%s personCount=%s detections=%s events=%s",
                     result["cameraId"],result["frameId"],result["personCount"],safe_detections,safe_events)

    async def inference_loop(self) -> None:
        next_allowed = 0.0
        while True:
            # Wait BEFORE taking a frame so arrivals replace stale waiting work.
            await asyncio.sleep(max(0.0, next_allowed - time.monotonic()))
            frame = await self.buffer.get_latest()
            if not self.current(frame):
                self.metrics.counts["stale"] += 1
                continue
            next_allowed = time.monotonic() + 1 / self.settings.max_fps
            job = asyncio.create_task(asyncio.to_thread(self.process_frame, frame))
            try:
                result, decode, inference, total = await asyncio.shield(job)
            except asyncio.CancelledError:
                # Threads cannot be cancelled: drain before reset/reconnect.
                await asyncio.gather(job, return_exceptions=True)
                raise
            except Exception as exc:
                model_error = getattr(getattr(self.engine, "manager", None), "status", None) == "failed"
                if hasattr(self.protocol,"error") and self.current(frame):
                    await self.ws.send(self.protocol.error(frame,model_error))
                self.metrics.counts["invalid"] += 1
                if model_error or not isinstance(exc,ValueError):
                    raise
                continue
            self.metrics.observe(decode, inference, total)
            if self.current(frame):
                await self.send_detection_result(result)
            else:
                self.metrics.counts["stale"] += 1

    async def monitor(self) -> None:
        ticks = 0
        while True:
            await asyncio.sleep(1)
            ticks += 1
            for camera_id,state in self.camera_states.items():
                if state["last_received"] and not state["offline"] and time.monotonic() - state["last_received"] > self.settings.offline_seconds:
                    self.invalidate_camera(camera_id)
                    state["data_status"] = "OFFLINE"
                    await self.send_status(camera_id,"OFFLINE")
                    log.info("Camera %s offline; pending work invalidated",camera_id)
                elif state["last_received"] and state["data_status"] == "LIVE" and time.monotonic() - state["last_received"] > self.settings.max_frame_age:
                    state["data_status"] = "STALE"
                    await self.send_status(camera_id,"STALE")
            if ticks % 10 == 0:
                summary = await asyncio.to_thread(self.metrics.snapshot, self.buffer.dropped)
                per_camera={camera_id:{"received":counts["received"],"sent":counts["sent"],
                    "status":self.camera_states[camera_id]["data_status"]}
                    for camera_id,counts in self.camera_metrics.items()}
                log.info("Worker metrics: %s cameraMetrics=%s", summary,per_camera)
            if hasattr(self.engine, "expire_state"):
                await asyncio.to_thread(self.engine.expire_state, time.time())

    async def handle_disconnect(self) -> None:
        self.metrics.connected = False
        if self.session_id:
            log.info("Worker WebSocket disconnected; cameras=%s",self.camera_ids)
        for camera_id in self.camera_ids:
            self.invalidate_camera(camera_id)
        self.session_id = ""
        await asyncio.to_thread(self.engine.reset)
        if self.ws is not None:
            await self.ws.close()
        self.ws = None

    async def run_session(self) -> None:
        self.session_id = str(uuid.uuid4())
        self._initialize_camera_states()
        self.ws = await self.connect()
        await self.register_worker()
        self.metrics.connected = True
        self.metrics.counts["connections"] += 1
        log.info("Worker WebSocket connected; inference ready")
        tasks = [asyncio.create_task(fn()) for fn in (self.receive_frames, self.inference_loop, self.monitor, self.stop_event.wait)]
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def reconnect_with_backoff(self, attempt: int) -> None:
        delay = min(30.0, 0.5 * 2 ** min(attempt, 6)) * random.uniform(0.8, 1.2)
        try:
            await asyncio.wait_for(self.stop_event.wait(), timeout=delay)
        except TimeoutError:
            pass

    async def run_forever(self) -> None:
        attempt = 0
        while not self.stop_event.is_set():
            started = time.monotonic()
            try:
                await self.run_session()
            except InvalidStatus as exc:
                status = exc.response.status_code
                terminal,message=classify_http_status(status)
                if terminal:
                    raise AuthenticationError(message) from None
                log.warning("%s; retrying",message)
            except ConnectionClosed as exc:
                code = exc.rcvd.code if exc.rcvd else None
                terminal,message=classify_close_code(code)
                if terminal:
                    raise AuthenticationError(message) from None
                log.warning("%s; reconnecting",message)
            except (OSError, TimeoutError) as exc:
                log.warning("Connection unavailable (%s, errno=%s); retrying", type(exc).__name__, getattr(exc, "errno", None))
            finally:
                await self.handle_disconnect()
            if time.monotonic() - started > 10:
                attempt = 0
            if not self.stop_event.is_set():
                await self.reconnect_with_backoff(attempt)
                attempt += 1

    async def stop(self) -> None:
        self.stop_event.set()
        if self.ws is not None:
            await self.ws.close()
