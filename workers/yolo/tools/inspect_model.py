"""Inspect exact selected model without opening a network connection."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json
from app import ROOT
from app.config import load_settings
from app.inference_manager import InferenceManager


def main():
    manager = InferenceManager(load_settings())
    try:
        manager.initialize()
        info = manager.engine.get_model_info()
        (ROOT/"reports").mkdir(exist_ok=True)
        (ROOT/"reports/model_info.json").write_text(json.dumps(info,indent=2),encoding="utf-8")
        print(json.dumps(info,indent=2))
    finally:
        manager.shutdown()


if __name__ == "__main__":
    main()
