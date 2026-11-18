"""Independent relay/Worker processes + Android packet emulator; localhost only."""
import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
import httpx
import psutil
from websockets.asyncio.client import connect
from app import ROOT
from app.demo_protocol import validate_demo_result
from mock_server.frame_source import demo_jpeg
from tools.android_simulator import camera_packet,CAMERA_ID


async def exercise(port,relay_start,relay_stop,worker):
    summaries=[]; latencies=[]; tracked=[]; modes=[]; rss=[]; cpu=[]
    worker_process=psutil.Process(worker.pid)
    def resources():
        # Windows venv python.exe can be a launcher with the real interpreter child.
        processes=[worker_process]+worker_process.children(recursive=True)
        memory=total_cpu=0.0
        for process in processes:
            try:
                memory+=process.memory_info().rss/1024**2
                times=process.cpu_times()
                total_cpu+=times.user+times.system
            except psutil.NoSuchProcess:
                pass
        return memory,total_cpu
    jpeg=demo_jpeg()
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}",trust_env=False,timeout=2) as http:
        async def ready():
            async with asyncio.timeout(15):
                while True:
                    if worker.poll() is not None: raise RuntimeError("Worker exited before test completed")
                    try:
                        response=await http.get("/status")
                        if response.status_code==200 and response.json()["workerConnected"]: return
                    except httpx.HTTPError: pass
                    await asyncio.sleep(.1)
        await ready()
        start=time.monotonic()
        _,previous_cpu=resources()
        previous_time=start
        segment_rates=[]
        stamps=[]
        for index,mode in enumerate(("ICN1","RAW_JPEG","demo-v0.3")):
            segment_stamps=[]
            async with connect(f"ws://127.0.0.1:{port}/ws/yolo/camera?cameraId={CAMERA_ID}&token=local-camera-demo",
                               additional_headers={"X-Camera-ID":str(CAMERA_ID)},proxy=None,compression=None) as camera:
                hello=json.loads(await camera.recv())
                assert hello==dict(type="hello",cameraId=CAMERA_ID,maxFps=10)
                for frame_id in range(1,7):
                    sent=time.monotonic()
                    await camera.send(camera_packet(jpeg,frame_id,mode))
                    async with asyncio.timeout(5):
                        while True:
                            response=(await http.get("/result")).json()
                            result=response.get("result")
                            if result and result["frameId"]==frame_id: break
                            await asyncio.sleep(.02)
                    validate_demo_result(result)
                    if result["personCount"]<1 or result["events"]: raise RuntimeError("Unexpected real model result")
                    latencies.append(result["inferMs"])
                    stamps.append(time.monotonic())
                    tracked.append(any(d["trackId"] is not None for d in result["detections"]))
                    segment_stamps.append(time.monotonic())
                    memory,total_cpu=resources()
                    sample_time=time.monotonic()
                    rss.append(memory)
                    cpu.append(max(0,total_cpu-previous_cpu)/(sample_time-previous_time)*100)
                    previous_cpu,previous_time=total_cpu,sample_time
                    await asyncio.sleep(max(0,1/3-(time.monotonic()-sent)))
                modes.append(mode)
                segment_rates.append((len(segment_stamps)-1)/(segment_stamps[-1]-segment_stamps[0]))
                summaries.append((await http.get("/status")).json()["counters"])
            if index==0:
                # Restart only our relay process; Worker must reconnect automatically.
                relay_stop()
                await asyncio.sleep(.4)
                relay_start()
                await ready()
        return dict(passed=all(tracked[i] for i in (3,4,5,9,10,11,15,16,17)),
            recordedAt=datetime.now(timezone.utc).isoformat(),protocol="demo-v0.3",backend="onnx_cpu",
            modes=modes,responses=len(latencies),personDetectedEveryFrame=True,trackedFrames=sum(tracked),
            relayRestartReconnected=True,inferMeanMs=sum(latencies)/len(latencies),inferMinMs=min(latencies),
            inferMaxMs=max(latencies),elapsedSeconds=time.monotonic()-start,
            responsesPerSecondIncludingRestart=len(latencies)/(time.monotonic()-start),
            steadyResponseFpsByMode=dict(zip(modes,segment_rates)),resourceScope="Worker process tree including Windows launcher",workerPeakRssMiB=max(rss),workerMeanCpuPercent=sum(cpu)/len(cpu),counters=summaries)


def main():
    sock=socket.socket(); sock.bind(("127.0.0.1",0)); port=sock.getsockname()[1]; sock.close()
    env=os.environ.copy()
    env.update(INFERENCE_BACKEND="onnx_cpu",ONNX_MODEL_PATH=str(ROOT/"models/best.onnx"),
        CLASS_MAP_PATH="",YOLO_PROTOCOL="demo-v0.3",WS_URL=f"ws://127.0.0.1:{port}/ws/yolo/worker",
        YOLO_WORKER_TOKEN="local-worker-demo",YOLO_CAMERA_TOKEN="local-camera-demo",CAMERA_ID=str(CAMERA_ID),
        MOCK_MODE="true",YOLO_MAX_FPS="3",ENABLE_TRACKING="true",ENABLE_GESTURE="false",
        WORKER_MODEL_VERSION="icn-v1-yolo11n-finger-gun",ALLOW_DEMO_MODEL_FALLBACK="false",
        PYTHONIOENCODING="utf-8")
    kwargs=dict(cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding="utf-8",
                creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    children=[]; relay_process=None
    def stop(child):
        if child and child.poll() is None:
            child.terminate()
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired: child.kill(); child.wait(timeout=5)
    def relay_start():
        nonlocal relay_process
        relay_process=subprocess.Popen([sys.executable,"-m","local_relay","--port",str(port)],**kwargs)
        children.append(relay_process)
    try:
        relay_start()
        worker=subprocess.Popen([sys.executable,"-m","app.main","--run-seconds","25"],**kwargs)
        children.append(worker)
        report=asyncio.run(exercise(port,relay_start,lambda:stop(relay_process),worker))
        output=worker.communicate(timeout=30)[0]
        report["workerExit"]=worker.returncode
        report["workerGracefulShutdown"]="resources released" in output
        report["passed"]=report["passed"] and worker.returncode==0 and report["workerGracefulShutdown"]
        (ROOT/"reports").mkdir(exist_ok=True)
        (ROOT/"reports/local_relay_demo.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        print(json.dumps(report,indent=2))
        if not report["passed"]: raise RuntimeError("Local relay demo failed")
    finally:
        for child in children: stop(child)
        for child in children:
            if child.stdout: child.stdout.close()


if __name__=="__main__": main()
