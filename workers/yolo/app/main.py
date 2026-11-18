"""Run with python -m app.main; Ctrl+C drains active inference and exits."""
import asyncio
import logging
from app.config import load_settings
from app.pipeline import FramePipeline
from app.ws_client import YoloWorkerClient


class YoloWorkerApp:
    def __init__(self):
        self.settings = load_settings()
        self.engine = FramePipeline(self.settings)
        self.client = YoloWorkerClient(self.settings, self.engine)
        self.closed = False

    async def initialize(self):
        await asyncio.to_thread(self.engine.load_model)

    async def receive_loop(self):
        await self.client.receive_frames()

    async def inference_loop(self):
        await self.client.inference_loop()

    async def send_result(self, result):
        await self.client.send_detection_result(result)

    async def shutdown(self):
        await self.stop()

    async def start(self):
        await asyncio.to_thread(self.engine.load_model)
        meta = self.engine.get_model_metadata()
        logging.info("Model=%s device=%s gesture_decisions=%s", meta["modelVersion"], meta["backend"], meta["gestureEnabled"])
        await self.client.run_forever()

    def process_frame(self, frame):
        return self.client.process_frame(frame)

    async def stop(self):
        if self.closed:
            return
        self.closed = True
        await self.client.stop()
        summary = await asyncio.to_thread(self.client.metrics.snapshot, self.client.buffer.dropped)
        logging.info("Final worker metrics: %s", summary)
        await asyncio.to_thread(self.engine.close)

    async def run_forever(self):
        try:
            await self.start()
        finally:
            await self.stop()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-seconds", type=float, default=0, help="Optional bounded local test; 0 runs forever")
    parser.add_argument("--check-config", action="store_true", help="Validate env/model/hello without opening WebSocket")
    args = parser.parse_args()
    if args.run_seconds < 0:
        parser.error("run-seconds must be nonnegative")
    from app.logging_config import configure_logging
    configure_logging()
    logging.getLogger("websockets").setLevel(logging.CRITICAL)
    async def run():
        app = YoloWorkerApp()
        if args.check_config:
            await app.initialize()
            meta=app.engine.get_model_metadata()
            logging.info("Offline config check passed: protocol=%s cameras=%s modelVersion=%s classes=%s tokenPresent=%s",
                app.settings.protocol,app.client.camera_ids,meta.get("modelVersion"),list(meta.get("classes",{}).values()),
                bool(app.settings.token))
            await app.stop()
            return
        if args.run_seconds:
            try:
                await asyncio.wait_for(app.run_forever(), args.run_seconds)
            except TimeoutError:
                logging.info("Bounded local run finished; resources released")
        else:
            await app.run_forever()
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logging.info("Worker stopped")
    except Exception as exc:
        # Do not print exceptions from remote servers that can echo secrets.
        logging.error("Worker stopped (%s): %s", type(exc).__name__, str(exc))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
