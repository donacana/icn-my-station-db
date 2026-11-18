"""Select and serialize exactly one inference backend for process lifetime."""
import logging
import threading
from app.config import resolve_backend, validate_settings

class InferenceManager:
    def __init__(self, settings):
        self.settings = validate_settings(settings)
        self.engine = None
        self.lock = threading.RLock()
        self.status = "not_initialized"
        self.backend = None
        self.reason = ""

    def select_backend(self):
        return resolve_backend(self.settings)

    def initialize(self):
        with self.lock:
            if self.status == "ready":
                return
            if self.status in {"failed", "closed"}:
                raise RuntimeError("Backend failed/closed; change settings and restart")
            try:
                self.backend, self.reason = self.select_backend()
                logging.getLogger(__name__).info("Selected %s: %s", self.backend, self.reason)
                if self.backend == "onnx_cpu":
                    from app.onnx_engine import OnnxInferenceEngine
                    self.engine = OnnxInferenceEngine(self.settings)
                else:
                    from app.torch_engine import TorchInferenceEngine
                    self.engine = TorchInferenceEngine(self.settings, self.backend)
                self.engine.load_model()
                self.status = "ready"
            except Exception:
                self.status = "failed"
                if self.engine:
                    self.engine.close()
                raise

    def infer_frame(self, image):
        with self.lock:
            self.initialize()
            try:
                return self.engine.infer(image)
            except Exception:
                self.status = "failed"
                self.engine.close()
                logging.getLogger(__name__).error("Backend %s failed; no silent fallback. Restart with onnx_cpu after correction.", self.backend)
                raise

    def get_backend_status(self):
        return {"status": self.status, "backend": self.backend, "selectionReason": self.reason}

    def shutdown(self):
        with self.lock:
            if self.engine:
                self.engine.close()
            self.status = "closed"
