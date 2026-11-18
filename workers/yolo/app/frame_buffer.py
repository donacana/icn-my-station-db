"""Event-loop-owned latest-only buffer, one waiting frame per camera."""
import asyncio
from collections import OrderedDict
from app.protocol import Frame


class LatestFrameBuffer:
    def __init__(self, max_cameras: int = 1):
        self.frames: OrderedDict[str, Frame] = OrderedDict()
        self.ready = asyncio.Event()
        self.dropped = 0
        self.max_cameras = max_cameras

    def put_latest(self, frame: Frame) -> None:
        if frame.camera_id in self.frames:
            self.dropped += 1
        elif len(self.frames) >= self.max_cameras:
            raise ValueError("Camera capacity exceeded")
        self.frames[frame.camera_id] = frame
        self.ready.set()

    async def get_latest(self) -> Frame:
        await self.ready.wait()
        _, frame = self.frames.popitem(last=False)
        if not self.frames:
            self.ready.clear()
        return frame

    def clear(self, camera_id=None) -> None:
        if camera_id is None:
            self.dropped += len(self.frames)
            self.frames.clear()
        elif camera_id in self.frames:
            self.dropped += 1
            self.frames.pop(camera_id)
        self.ready.clear()
        if self.frames:
            self.ready.set()

    def get_dropped_count(self) -> int:
        return self.dropped
