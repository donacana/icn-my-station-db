"""Download one documented public-domain test image, never camera media."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import hashlib
import urllib.request
from app import ROOT

URL = "https://raw.githubusercontent.com/scikit-image/scikit-image/v0.19.3/skimage/data/astronaut.png"


def main():
    target = ROOT / "tests/assets/astronaut.png"
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():
        with urllib.request.urlopen(URL,timeout=30) as response:
            data = response.read(2*1024*1024+1)
        if len(data)>2*1024*1024 or not data.startswith(b"\x89PNG"):
            raise ValueError("Unexpected sample image")
        target.write_bytes(data)
    print("Public-domain NASA sample SHA256:",hashlib.sha256(target.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
