"""Optional Torch backend. Imported only after explicit startup selection."""
import gc
import time
import subprocess
from app.config import model_path
from app.inference_base import Detection, InferenceEngine, class_names


def check_cuda_compatibility(min_free_mb=512):
    status = {"usable": False}
    try:
        import torch
        status.update(torchVersion=torch.__version__, builtCuda=torch.version.cuda,
                      available=torch.cuda.is_available(), architectures=torch.cuda.get_arch_list())
        if not status["available"]:
            status["reason"] = "CUDA unavailable"
            return status
        capability = torch.cuda.get_device_capability(0)
        status.update(name=torch.cuda.get_device_name(0), capability=list(capability))
        # Kernel execution is decisive; compatible lower-minor SASS may run on sm_61.
        tensor = torch.ones((32,32),device="cuda")
        result = (tensor @ tensor).cpu()
        status["kernelSucceeded"] = bool(result[0,0].item() == 32)
        del tensor,result
        torch.cuda.empty_cache()
        free,total = torch.cuda.mem_get_info()
        status.update(freeMiB=free/2**20,totalMiB=total/2**20)
        available_mb = free/2**20
        try:
            probe = subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                capture_output=True,text=True,timeout=3,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            if probe.returncode == 0:
                status["nvidiaSmiFreeMiB"] = float(probe.stdout.splitlines()[0])
                available_mb = min(available_mb,status["nvidiaSmiFreeMiB"])
        except (OSError,ValueError,subprocess.TimeoutExpired):
            pass
        status["usable"] = status["kernelSucceeded"] and available_mb >= min_free_mb
        status["reason"] = "kernel and VRAM passed" if status["usable"] else "insufficient free VRAM"
    except Exception as exc:
        status["reason"] = type(exc).__name__
    return status


class TorchInferenceEngine(InferenceEngine):
    def __init__(self, settings, backend="torch_cpu"):
        self.settings, self.backend = settings, backend
        self.model = None
        self.cuda_status = None
        self.first_inference = True

    def check_cuda_compatibility(self):
        return check_cuda_compatibility(self.settings.min_vram_mb)

    def check_available_vram(self):
        import torch
        return torch.cuda.mem_get_info()[0]/2**20

    def load_model(self):
        if self.model is not None:
            return
        start = time.perf_counter()
        import torch
        from ultralytics import YOLO
        torch.set_num_threads(self.settings.intra_threads)
        self.device = "cuda:0" if self.backend == "torch_cuda" else "cpu"
        if self.backend == "torch_cuda":
            self.cuda_status = self.check_cuda_compatibility()
            if not self.cuda_status["usable"]:
                raise RuntimeError("CUDA preflight failed: " + self.cuda_status["reason"] + "; restart with onnx_cpu")
        self.path = model_path(self.settings,self.backend)
        model = YOLO(str(self.path),task="detect")
        self.names = class_names(model.names,self.settings.class_map_path)
        self.model = model
        self.load_ms = (time.perf_counter()-start)*1000

    def run_inference(self, frame):
        import torch
        with torch.inference_mode():
            return self.model.predict(source=frame, device=self.device, imgsz=self.settings.imgsz,
                conf=self.settings.conf, iou=self.settings.iou, half=False, batch=1,
                rect=False, max_det=300, save=False, verbose=False)[0]

    def infer(self, frame):
        self.load_model()
        try:
            if self.backend == "torch_cuda" and self.first_inference:
                if self.check_available_vram() < self.settings.min_vram_mb:
                    raise RuntimeError("Insufficient VRAM immediately before inference; restart with onnx_cpu")
            result = self.run_inference(frame)
            self.first_inference = False
            return [Detection(int(b.cls.item()),self.names[int(b.cls.item())],float(b.conf.item()),
                              tuple(map(float,b.xyxy[0].tolist()))) for b in result.boxes]
        except Exception:
            self.close()
            raise

    def get_class_names(self):
        self.load_model()
        return dict(self.names)

    def get_model_info(self):
        self.load_model()
        return {"backend":self.backend,"modelVersion":self.path.stem,"modelPath":str(self.path),
                "effectiveInputHW":[self.settings.imgsz,self.settings.imgsz],"device":self.device,
                "classes":self.names,"loadMs":self.load_ms,"cudaPreflight":self.cuda_status}

    def close(self):
        self.model = None
        gc.collect()
        if self.backend == "torch_cuda":
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
