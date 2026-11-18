"""One backend per process, >=30s steady-state test on the same public sample."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse
import hashlib
import json
import time
from dataclasses import replace
import numpy as np
import psutil
from app import ROOT
from app.config import load_settings
from app.inference_manager import InferenceManager
from app.metrics import Metrics
from mock_server.frame_source import FrameSource


def run(args):
    settings=replace(load_settings(),backend=args.backend,imgsz=args.imgsz,intra_threads=args.threads)
    manager=InferenceManager(settings)
    report={"backend":args.backend,"requestedImgsz":args.imgsz,"threads":args.threads,"status":"failed"}
    process=psutil.Process()
    source=FrameSource(image=args.image)
    image=source.next_image()
    source.close()
    # Never persist arbitrary user-supplied sample boxes/identities.
    public_sample = args.image is None
    try:
        start=time.perf_counter()
        manager.initialize()
        report["loadMs"]=(time.perf_counter()-start)*1000
        info=manager.engine.get_model_info()
        report["modelInfo"]=info
        report["modelSha256"]=hashlib.sha256(Path(info["modelPath"]).read_bytes()).hexdigest()
        report["inputSha256"]=hashlib.sha256(image.tobytes()).hexdigest() if public_sample else "private-not-recorded"
        start=time.perf_counter()
        first=manager.infer_frame(image)
        report["initialInferenceMs"]=(time.perf_counter()-start)*1000
        for _ in range(5):
            manager.infer_frame(image)
        samples=[]
        cpu_start=sum(process.cpu_times()[:2])
        start=time.perf_counter()
        peak_rss=0
        while time.perf_counter()-start<args.seconds:
            t=time.perf_counter()
            result=manager.infer_frame(image)
            samples.append((time.perf_counter()-t)*1000)
            peak_rss=max(peak_rss,process.memory_info().rss)
            if len(samples)%100==0 and psutil.virtual_memory().available<512*2**20:
                raise RuntimeError("Low available RAM; benchmark stopped")
        elapsed=time.perf_counter()-start
        cpu_seconds=sum(process.cpu_times()[:2])-cpu_start
        mean=float(np.mean(samples))
        report.update(status="passed",durationSeconds=elapsed,iterations=len(samples),meanMs=mean,
            minMs=min(samples),maxMs=max(samples),p95Ms=float(np.percentile(samples,95)),fps=len(samples)/elapsed,
            cpuProcessPercent=cpu_seconds/elapsed*100,cpuMachineEquivalentPercent=cpu_seconds/elapsed*100/psutil.cpu_count(),
            peakRssMiB=peak_rss/2**20,personCount=sum(d.class_name=="person" for d in result),
            resources=Metrics().snapshot())
        if public_sample:
            report["publicSampleDetections"]=[{"classId":d.class_id,"confidence":d.confidence,"bbox":d.bbox_xyxy} for d in result]
    except (ImportError,FileNotFoundError) as exc:
        report.update(status="skipped",reason=str(exc))
    except Exception as exc:
        report.update(status="failed",reason=type(exc).__name__+": "+str(exc))
    finally:
        manager.shutdown()
    target=ROOT/"reports"/f"benchmark_{args.backend}_{args.imgsz}_t{args.threads}.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k not in {"modelInfo","publicSampleDetections"}},indent=2))
    return 1 if report["status"]=="failed" else 0


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--backend",choices=["onnx_cpu","torch_cpu","torch_cuda"],default="onnx_cpu")
    parser.add_argument("--imgsz",type=int,default=416)
    parser.add_argument("--threads",type=int,default=4)
    parser.add_argument("--seconds",type=float,default=30)
    parser.add_argument("--image",type=Path)
    args=parser.parse_args()
    if args.seconds<30:
        parser.error("Steady-state measurement must be at least 30 seconds")
    raise SystemExit(run(args))
