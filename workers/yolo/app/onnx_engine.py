"""ONNX Runtime CPU only; no Torch or Ultralytics imports."""
import ast
import time
import numpy as np
import onnxruntime as ort
from app.config import Settings, model_path
from app.inference_base import InferenceEngine, class_names
from app.preprocessing import letterbox
from app.postprocessing import postprocess


class OnnxInferenceEngine(InferenceEngine):
    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = None
        self.last_class_max = {}

    def load_model(self):
        if self.session is not None:
            return
        start = time.perf_counter()
        path = model_path(self.settings, "onnx_cpu")
        if "CPUExecutionProvider" not in ort.get_available_providers():
            raise RuntimeError("ONNX CPUExecutionProvider unavailable")
        options = ort.SessionOptions()
        options.intra_op_num_threads = self.settings.intra_threads
        options.inter_op_num_threads = self.settings.inter_threads
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.add_session_config_entry("session.intra_op.allow_spinning", "0")
        options.add_session_config_entry("session.inter_op.allow_spinning", "0")
        session = ort.InferenceSession(str(path), sess_options=options, providers=["CPUExecutionProvider"])
        inputs, outputs = session.get_inputs(), session.get_outputs()
        if len(inputs) != 1 or len(outputs) != 1 or inputs[0].type != "tensor(float)":
            raise ValueError("Supported: one FP32 NCHW input, one Detect output")
        shape = inputs[0].shape
        if len(shape) != 4 or (isinstance(shape[0], int) and shape[0] != 1) or shape[1] != 3:
            raise ValueError("Expected batch=1 channels=3 NCHW input")
        hw = tuple(v if isinstance(v, int) else self.settings.imgsz for v in shape[2:])
        if any(v < 32 or v > 1920 or v % 32 for v in hw):
            raise ValueError("Input dimensions must be supported multiples of 32")
        meta = session.get_modelmeta().custom_metadata_map
        if meta.get("task") != "detect":
            raise ValueError("Only task=detect models supported")
        names = class_names(meta.get("names"), self.settings.class_map_path)
        args = ast.literal_eval(meta.get("args", "{}"))
        if not isinstance(args, dict):
            raise ValueError("Invalid export args metadata")
        if "Ultralytics" not in meta.get("description", ""):
            raise ValueError("Unverified exporter; require Ultralytics YOLO11 Detect export")
        nms = args.get("nms")
        output_shape = outputs[0].shape
        if type(nms) is bool:
            layout = "nms_bnc" if nms else "raw_bcn"
        elif nms is None and len(output_shape)==3 and output_shape[1] == 4+len(names):
            # Ultralytics 8.4 uses nms=None for a normal raw Detect export.
            # [B,4+classes,predictions] proves NMS has not been embedded.
            layout = "raw_bcn"
            nms = False
        else:
            raise ValueError("Cannot prove whether ONNX output includes NMS")
        probe = session.run(None, {inputs[0].name: np.zeros((1, 3, *hw), dtype=np.float32)})[0]
        _, info = letterbox(np.zeros((32, 32, 3), np.uint8), hw)
        postprocess(probe, names, info, self.settings.conf, self.settings.iou, layout)
        self.session, self.path, self.names = session, path, names
        self.input_name, self.hw, self.layout = inputs[0].name, hw, layout
        self.info = {"backend": "onnx_cpu", "modelVersion": path.stem, "modelPath": str(path),
                     "providers": session.get_providers(), "inputName": inputs[0].name,
                     "inputType": inputs[0].type, "inputShape": shape, "effectiveInputHW": hw,
                     "outputName": outputs[0].name, "outputShape": outputs[0].shape,
                     "actualOutputShape": list(probe.shape), "layout": layout,
                     "coordinates": "xyxy input pixels" if args["nms"] else "center xywh input pixels",
                     "nmsIncluded": nms, "dynamicInput": any(not isinstance(x, int) for x in shape),
                     "classes": names, "loadMsIncludingProbe": (time.perf_counter() - start) * 1000}

    def get_input_shape(self):
        self.load_model()
        return (1, 3, *self.hw)

    def preprocess(self, frame):
        return letterbox(frame, self.hw)

    def run_inference(self, tensor):
        return self.session.run(None, {self.input_name: tensor})[0]

    def postprocess(self, output, info):
        thresholds={class_id:(self.settings.person_conf if name=="person" else self.settings.conf)
                    for class_id,name in self.names.items()}
        return postprocess(output, self.names, info, thresholds, self.settings.iou, self.layout)

    def infer(self, frame):
        self.load_model()
        tensor, info = self.preprocess(frame)
        output=self.run_inference(tensor)
        if self.layout=="raw_bcn":
            self.last_class_max={self.names[i]:float(output[0,4+i].max()) for i in self.names}
        else:
            rows=output[0]
            self.last_class_max={name:max((float(row[4]) for row in rows if int(row[5])==i),default=0.0)
                                 for i,name in self.names.items()}
        return self.postprocess(output, info)

    def get_last_diagnostics(self):
        return {"classMaxConfidence":dict(self.last_class_max)}

    def get_class_names(self):
        self.load_model()
        return dict(self.names)

    def get_model_info(self):
        self.load_model()
        return dict(self.info)

    def close(self):
        self.session = None
