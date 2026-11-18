"""Windows YOLO11n worker. Keep library state inside this workspace."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for directory in (ROOT / ".cache" / "ultralytics", ROOT / ".cache" / "matplotlib"):
    directory.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".cache" / "ultralytics"))
os.environ.setdefault("YOLO_AUTOINSTALL", "false")
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache" / "matplotlib"))
