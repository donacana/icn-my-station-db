"""Read-only hardware/package inventory; writes only workspace report."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse
import importlib.metadata
import json
import platform
import shutil
import subprocess
import psutil
from app import ROOT


def command(args):
    try:
        r = subprocess.run(args,capture_output=True,text=True,timeout=20,
                           creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        return r.stdout.strip() if r.returncode==0 else "unavailable"
    except (OSError,subprocess.TimeoutExpired):
        return "unavailable"


def inspect(cuda=False):
    memory = psutil.virtual_memory()
    info = {"os":platform.platform(),"python":sys.version,"executable":sys.executable,
            "cpu":command(["powershell","-NoProfile","-Command","(Get-CimInstance Win32_Processor).Name"]),
            "physicalCores":psutil.cpu_count(logical=False),"logicalThreads":psutil.cpu_count(),
            "totalRamGiB":memory.total/2**30,"availableRamGiB":memory.available/2**30,
            "diskFreeGiB":shutil.disk_usage(ROOT).free/2**30,
            "gpu":command(["nvidia-smi","--query-gpu=name,memory.total,memory.used,driver_version","--format=csv,noheader"]),
            "pythonInstallations":command(["py","-0p"]),"pip":command([sys.executable,"-m","pip","--version"]),
            "packages":{d.metadata["Name"]:d.version for d in importlib.metadata.distributions()}}
    if cuda:
        from app.torch_engine import check_cuda_compatibility
        info["cuda"] = check_cuda_compatibility()
    return info


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--cuda",action="store_true")
    args=parser.parse_args()
    info=inspect(args.cuda)
    (ROOT/"reports").mkdir(exist_ok=True)
    filename="hardware_torch.json" if args.cuda else "hardware.json"
    (ROOT/"reports"/filename).write_text(json.dumps(info,indent=2),encoding="utf-8")
    print(json.dumps(info,indent=2))
