import asyncio
from app.frame_buffer import LatestFrameBuffer
from app.protocol import Frame


def test_latest_per_camera():
    async def run():
        b=LatestFrameBuffer(2)
        for i in range(100): b.put_latest(Frame("a",i,1,b""))
        b.put_latest(Frame("b",1,1,b""))
        assert len(b.frames)==2 and b.get_dropped_count()==99
        assert (await b.get_latest()).frame_id==99
        assert (await b.get_latest()).camera_id=="b"
        b.clear(); assert not b.ready.is_set()
    asyncio.run(run())
