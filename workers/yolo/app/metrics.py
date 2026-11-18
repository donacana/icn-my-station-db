"""Aggregate only: never retain JPEGs, tokens or object identities."""
import subprocess
import time
from collections import defaultdict
import psutil


class Metrics:
    def __init__(self):
        self.started = time.monotonic()
        self.counts = defaultdict(int)
        self.totals = defaultdict(float)
        self.connected = False
        self.process = psutil.Process()
        self.process.cpu_percent()

    def observe(self, decode_ms: float, inference_ms: float, total_ms: float) -> None:
        self.counts["processed"] += 1
        for key, value in (("decodeMs", decode_ms), ("inferenceMs", inference_ms), ("processingMs", total_ms)):
            self.totals[key] += value

    def snapshot(self, dropped: int = 0) -> dict:
        elapsed = max(time.monotonic() - self.started, 1e-9)
        n = self.counts["processed"]
        gpu = None
        try:
            proc = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
                                  capture_output=True, text=True, timeout=2,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if proc.returncode == 0:
                util, used, total = map(int, proc.stdout.strip().splitlines()[0].split(","))
                gpu = {"utilizationPercent": util, "usedMiB": used, "totalMiB": total}
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
        return {**dict(self.counts), "elapsedSeconds": elapsed, "processingFps": n / elapsed,
                "receiveFps": self.counts["received"] / elapsed, "droppedWaiting": dropped,
                **{key: val / max(n, 1) for key, val in self.totals.items()},
                "cpuProcessPercent": self.process.cpu_percent(), "rssMiB": self.process.memory_info().rss / 2**20,
                "gpu": gpu, "connected": self.connected}
