"""Repeat public packaged demo JPEG in memory and validate worker responses."""
import argparse
import asyncio
import hmac
import json
import logging
import time

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed
from app.protocol import Frame, encode_frame, validate_result_message


from mock_server.frame_source import demo_jpeg, FrameSource


class MockServer:
    def __init__(self, jpeg: bytes, camera_id="DEMO_T1_3", frames=12, fps=3.0,
                 disconnect_after=0, token="", result_timeout=30.0):
        self.jpeg, self.camera_id, self.frames, self.fps = jpeg, camera_id, frames, fps
        self.disconnect_after, self.token = disconnect_after, token
        self.result_timeout = result_timeout
        self.connections = 0
        self.results: list[dict] = []  # aggregate values only, no detections/identities
        self.errors: list[str] = []
        self.sessions: set[str] = set()
        self.done = asyncio.Event()

    async def handler(self, ws):
        if ws.request.path != "/ws/yolo/worker":
            await ws.close(1008, "Unknown route")
            return
        if self.token and not hmac.compare_digest(ws.request.headers.get("Authorization", ""), f"Bearer {self.token}"):
            await ws.close(4401, "Unauthorized")
            return
        try:
            registration = json.loads(await asyncio.wait_for(ws.recv(), 10))
            if (registration.get("type") != "register" or registration.get("protocol") != "mock-v1"
                    or registration.get("cameraId") != self.camera_id or not registration.get("sessionId")):
                await ws.close(1008, "Invalid registration")
                return
            session = registration["sessionId"]
            if session in self.sessions:
                raise ValueError("Session not renewed")
            self.sessions.add(session)
            self.connections += 1
            await ws.send(json.dumps({"type": "registered", "protocol": "mock-v1"}))
            sent = set()
            count = self.disconnect_after if self.disconnect_after and self.connections == 1 else self.frames
            async def producer():
                for i in range(count):
                    sent.add(i)
                    await ws.send(encode_frame(Frame(self.camera_id, i, int(time.time() * 1000), (self.jpeg() if callable(self.jpeg) else self.jpeg))))
                    await asyncio.sleep(1 / self.fps)
            producer_task = asyncio.create_task(producer())
            last = -1
            try:
                while last < count - 1:
                    raw = await asyncio.wait_for(ws.recv(), self.result_timeout)
                    result = json.loads(raw)
                    if result.get("type") == "camera_status":
                        if result.get("personCount") is not None or result.get("status") not in {"STALE", "OFFLINE"}:
                            raise ValueError("Invalid status")
                        continue
                    validate_result_message(result)
                    if (result["cameraId"] != self.camera_id or result["sessionId"] != session
                            or result["frameId"] not in sent or result["frameId"] <= last):
                        raise ValueError("Response identity/order mismatch")
                    last = result["frameId"]
                    self.results.append({"personCount": result["personCount"], "inferenceMs": result["inferenceMs"],
                                         "trackedPersons": sum(d["className"] == "person" and d["trackId"] is not None for d in result["detections"]),
                                         "eventCount": len(result["events"])})
                if self.disconnect_after and self.connections == 1:
                    await ws.close(1012, "Mock reconnect test")
                else:
                    self.done.set()
                    await ws.wait_closed()
            finally:
                producer_task.cancel()
                await asyncio.gather(producer_task, return_exceptions=True)
        except ConnectionClosed:
            pass
        except Exception as exc:
            self.errors.append(type(exc).__name__)
            self.done.set()
            await ws.close(1011, "Mock validation failed")


async def run(args):
    import os
    source = FrameSource(image=args.image, video=args.video, generated=args.generated)
    server = MockServer(source.next_jpeg, frames=args.frames, disconnect_after=args.disconnect_after,
                        token=os.getenv("WS_TOKEN", ""), fps=args.fps, camera_id=args.camera_id)
    try:
        async with serve(server.handler, "127.0.0.1", args.port, max_size=2**20, compression=None):
            print(f"LOCAL MOCK listening on 127.0.0.1:{args.port}; configured local test source", flush=True)
            await server.done.wait()
            print(json.dumps({"connections": server.connections, "responses": len(server.results), "errors": server.errors}))
            if server.errors:
                raise RuntimeError("Mock validation failed")
    finally:
        source.close()



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--fps", type=float, default=3.0)
    parser.add_argument("--camera-id", default="DEMO_T1_3")
    parser.add_argument("--image")
    parser.add_argument("--video")
    parser.add_argument("--generated", action="store_true")
    parser.add_argument("--frames", type=int, default=12)
    parser.add_argument("--disconnect-after", type=int, default=0)
    args = parser.parse_args()
    if args.frames < 1 or args.disconnect_after < 0 or not 0 < args.fps <= 120:
        parser.error("Invalid frame counts")
    logging.getLogger("websockets").setLevel(logging.CRITICAL)
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
