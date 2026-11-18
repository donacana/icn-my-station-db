"""Torch-free ByteTrack adapter; camera/session-scoped transient state."""
import math
from dataclasses import replace
import numpy as np
import supervision as sv
from trackers import ByteTrackTracker
from app.inference_base import Detection

class PersonTracker:
    def __init__(self, fps=3.0, retention=2.0, confidence=0.35, max_cameras=8):
        self.fps, self.retention, self.confidence = fps, retention, confidence
        self.max_cameras = max_cameras
        self.states = {}
        self.next_id = 1

    def update_tracks(self, camera_id: str, detections: list[Detection], session_id: str = "default", timestamp: float = 0.0):
        if not math.isfinite(timestamp):
            raise ValueError("Invalid tracking timestamp")
        for camera, state in list(self.states.items()):
            if timestamp - state["last"] > self.retention:
                self.states.pop(camera)
        state = self.states.get(camera_id)
        if state is None or state["session"] != session_id:
            if state is None and len(self.states) >= self.max_cameras:
                raise ValueError("Tracking camera capacity exceeded")
            state = {"session": session_id, "last": float("-inf"), "active": [], "ids": {},
                     "tracker": ByteTrackTracker(lost_track_buffer=max(1, round(self.retention * 30)),
                       frame_rate=self.fps, track_activation_threshold=self.confidence,
                       high_conf_det_threshold=self.confidence, minimum_consecutive_frames=1)}
            self.states[camera_id] = state
        if timestamp <= state["last"]:
            raise ValueError("Tracking timestamps must increase")
        state["last"] = timestamp
        indices = [i for i,d in enumerate(detections) if d.class_name == "person"]
        persons = [detections[i] for i in indices]
        data = sv.Detections(xyxy=np.array([d.bbox_xyxy for d in persons], dtype=np.float32).reshape(-1,4),
            confidence=np.array([d.confidence for d in persons], dtype=np.float32),
            class_id=np.array([d.class_id for d in persons], dtype=int),
            data={"source_index": np.array(indices, dtype=int)})
        tracked = state["tracker"].update(data, timestamp=timestamp)
        result = list(detections)
        for index, tid in zip(tracked.data.get("source_index", []), tracked.tracker_id):
            public_id = None
            if tid >= 0:
                if int(tid) not in state["ids"]:
                    state["ids"][int(tid)] = self.next_id
                    self.next_id += 1
                public_id = state["ids"][int(tid)]
            result[int(index)] = replace(result[int(index)], track_id=public_id)
        alive = {t.tracker_id for t in state["tracker"].tracks}
        state["ids"] = {k:v for k,v in state["ids"].items() if k in alive}
        state["active"] = [d for d in result if d.class_name == "person" and d.track_id is not None]
        return result

    def get_active_tracks(self, camera_id, timestamp=None):
        state = self.states.get(camera_id)
        if state and (timestamp is None or timestamp - state["last"] <= self.retention):
            return list(state["active"])
        if state:
            self.states.pop(camera_id, None)
        return []

    def reset_tracking(self, camera_id=None):
        if camera_id is None:
            self.states.clear()
        else:
            self.states.pop(camera_id, None)

    def get_tracking_status(self):
        return {"algorithm": "trackers.ByteTrackTracker", "cameras": len(self.states), "retentionSeconds": self.retention}
