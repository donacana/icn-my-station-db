"""Compare only matching-input, matching-resolution exports of the same weights."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json
from app import ROOT


def iou(a,b):
    inter=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    union=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter
    return inter/max(union,1e-9)


def compare(onnx_report,torch_report,provenance):
    if any(r.get("status")!="passed" for r in (onnx_report,torch_report)):
        raise ValueError("Both benchmarks must pass")
    if (onnx_report["modelSha256"]!=provenance["sha256"] or torch_report["modelSha256"]!=provenance["sourceSha256"]):
        raise ValueError("Not proven to originate from identical weights")
    if (onnx_report["inputSha256"]!=torch_report["inputSha256"] or onnx_report["modelInfo"]["effectiveInputHW"]!=torch_report["modelInfo"]["effectiveInputHW"]):
        raise ValueError("Input data or effective resolution differs")
    a,b=onnx_report["publicSampleDetections"],torch_report["publicSampleDetections"]
    matched=set(); pairs=[]
    for det in a:
        choices=[(iou(det["bbox"],other["bbox"]),i) for i,other in enumerate(b) if i not in matched and other["classId"]==det["classId"]]
        score,index=max(choices,default=(0,-1))
        if index>=0 and score>=.5:
            matched.add(index)
            pairs.append({"iou":score,"confidenceDifference":abs(det["confidence"]-b[index]["confidence"])})
    return {"backend":torch_report["backend"],"sameWeightsVerified":True,"sameInputVerified":True,
            "onnxDetections":len(a),"torchDetections":len(b),"matched":len(pairs),"pairs":pairs,
            "scope":"single public sample, not accuracy validation"}


def main():
    provenance=json.loads((ROOT/"models/yolo11n.source.json").read_text())
    base=json.loads((ROOT/"reports/benchmark_onnx_cpu_416_t4.json").read_text())
    results=[]
    for backend in ("torch_cpu","torch_cuda"):
        path=ROOT/"reports"/f"benchmark_{backend}_416_t4.json"
        if path.exists():
            results.append(compare(base,json.loads(path.read_text()),provenance))
    (ROOT/"reports/backend_comparison.json").write_text(json.dumps(results,indent=2),encoding="utf-8")
    print(json.dumps(results,indent=2))


if __name__=="__main__":
    main()
