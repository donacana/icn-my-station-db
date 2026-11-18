"""Verify separate Mock and Worker CLI processes with bounded cleanup."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json
import os
import socket
import subprocess
from app import ROOT


def main():
    sock=socket.socket(); sock.bind(("127.0.0.1",0)); port=sock.getsockname()[1]; sock.close()
    env=os.environ.copy()
    env.update(INFERENCE_BACKEND="onnx_cpu",WS_URL=f"ws://127.0.0.1:{port}/ws/yolo/worker",
               WS_TOKEN="",CAMERA_ID="DEMO_T1_3",MOCK_MODE="true",PYTHONIOENCODING="utf-8")
    children=[]
    kwargs=dict(cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding="utf-8",
                creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    try:
        mock=subprocess.Popen([sys.executable,"-m","mock_server.server","--port",str(port),"--frames","9","--disconnect-after","3"],**kwargs)
        children.append(mock)
        worker=subprocess.Popen([sys.executable,"-m","app.main","--run-seconds","10"],**kwargs)
        children.append(worker)
        mock_output=mock.communicate(timeout=30)[0]
        worker_output=worker.communicate(timeout=20)[0]
        summaries=[json.loads(line) for line in mock_output.splitlines() if line.startswith('{')]
        summary=summaries[-1] if summaries else {}
        passed=(mock.returncode==0 and worker.returncode==0 and summary.get("connections")==2
                and summary.get("responses",0)>0 and not summary.get("errors")
                and "resources released" in worker_output)
        report={"passed":passed,"mockExit":mock.returncode,"workerExit":worker.returncode,"mock":summary,
                "boundedShutdown": "resources released" in worker_output}
        (ROOT/"reports").mkdir(exist_ok=True)
        (ROOT/"reports/process_demo.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        print(json.dumps(report,indent=2))
        if not passed:
            print(mock_output)
            print(worker_output)
            raise RuntimeError("Independent process integration failed")
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
                try: child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill(); child.wait()


if __name__=="__main__":
    main()
