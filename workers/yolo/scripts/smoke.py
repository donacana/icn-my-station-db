"""Real YOLO -> ByteTrack -> loopback WS integration and reconnect benchmark."""
import argparse
import asyncio
import json
from dataclasses import replace
from websockets.asyncio.server import serve
from app import ROOT
from app.config import Settings
from app.pipeline import FramePipeline
from app.ws_client import YoloWorkerClient
from mock_server.server import MockServer, demo_jpeg


async def run(backend="onnx_cpu"):
    settings = Settings(backend=backend)
    engine = FramePipeline(settings)
    await asyncio.to_thread(engine.load_model)
    jpeg = demo_jpeg()
    # Warmup runs in the same selected backend, outside timed WebSocket traffic.
    from app.preprocessing import decode_jpeg
    await asyncio.to_thread(engine.manager.infer_frame, decode_jpeg(jpeg))
    engine.reset()
    mock = MockServer(jpeg, frames=15, disconnect_after=3)
    async with serve(mock.handler, "127.0.0.1", 0, compression=None) as server:
        port = server.sockets[0].getsockname()[1]
        client = YoloWorkerClient(replace(settings, ws_url=f"ws://127.0.0.1:{port}/ws/yolo/worker"), engine)
        task = asyncio.create_task(client.run_forever())
        try:
            await asyncio.wait_for(mock.done.wait(), 90)
            if mock.errors or mock.connections < 2 or not mock.results:
                raise AssertionError("Mock/reconnect failed")
            if not all(r["personCount"] > 0 and r["eventCount"] == 0 for r in mock.results) or not any(r["trackedPersons"] > 0 for r in mock.results):
                raise AssertionError("Real person/tracking verification failed")
        finally:
            await client.stop()
            await asyncio.wait_for(task, 30)
        report = {"backend": engine.manager.backend, "model": engine.manager.engine.get_model_info()["modelVersion"], "inputSize": [640, 360],
                  "inputFps": 3, "connections": mock.connections, "responses": len(mock.results),
                  "personCounts": sorted({r["personCount"] for r in mock.results}),
                  "errors": mock.errors, "metrics": client.metrics.snapshot(client.buffer.dropped)}
        output = ROOT / "reports" / f"smoke_{backend}.json"
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        engine.close()
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["onnx_cpu", "torch_cpu", "torch_cuda"], default="onnx_cpu")
    asyncio.run(run(parser.parse_args().backend))
