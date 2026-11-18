"""Run in .venv-model; exported ONNX does not need Torch at runtime."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import argparse
import hashlib
import json
from app import ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=ROOT / "models/yolo11n.pt")
    parser.add_argument("--imgsz", type=int, default=416)
    parser.add_argument("--fixed", action="store_true")
    args = parser.parse_args()
    if not args.model.is_file():
        raise FileNotFoundError("Prepare trusted .pt weights first")
    from ultralytics import YOLO
    import onnx
    model = YOLO(str(args.model))
    output = Path(model.export(format="onnx", imgsz=args.imgsz, dynamic=not args.fixed,
                              simplify=False, opset=17, nms=False, device="cpu", batch=1, half=False))
    onnx.checker.check_model(onnx.load(str(output)))
    info = {"source": args.model.name, "sourceSha256": hashlib.sha256(args.model.read_bytes()).hexdigest(),
            "output": output.name, "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "dynamic": not args.fixed, "nms": False, "imgsz": args.imgsz, "opset": 17}
    output.with_suffix(".source.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
