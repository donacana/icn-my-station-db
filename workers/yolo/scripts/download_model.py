"""Download ONLY official YOLO11n weights, with size ceiling and atomic replace."""
import hashlib
import json
import urllib.request
from app import ROOT

URL = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt"


def main():
    target = ROOT / "models/yolo11n.pt"
    target.parent.mkdir(exist_ok=True)
    if target.exists():
        print("YOLO11n already exists; no overwrite")
        return
    with urllib.request.urlopen(URL, timeout=60) as response:
        length = int(response.headers.get("Content-Length", "0"))
        if not 0 < length <= 10 * 1024 * 1024:
            raise ValueError("Unexpected model download size")
        print(f"Official Ultralytics YOLO11n download: {length} bytes")
        payload = response.read(10 * 1024 * 1024 + 1)
        if len(payload) != length:
            raise ValueError("Model download length mismatch")
    temp = target.with_suffix(".part")
    temp.write_bytes(payload)
    temp.replace(target)
    (ROOT / "models/source.json").write_text(json.dumps({"url": URL, "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest()}, indent=2), encoding="utf-8")
    print("Saved models/yolo11n.pt and source hash")


if __name__ == "__main__":
    main()
