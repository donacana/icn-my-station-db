"""Common decode/detect/track/count/gesture pipeline for every backend."""
import threading
import time
import logging
from app.inference_manager import InferenceManager
from app.preprocessing import decode_jpeg, normalize_bbox
from app.tracking import PersonTracker
from app.gesture import GestureStateMachine
from app.counting import build_count_result
from app.protocol import build_detection_message

class FramePipeline:
    def __init__(self, settings):
        self.settings = settings
        self.manager = InferenceManager(settings)
        self.lock = threading.RLock()
        self.tracker = PersonTracker(settings.max_fps, settings.track_retention, settings.person_conf)
        self.contexts = {}
        self.last_captured = {}
        self.gesture = None

    def load_model(self):
        self.manager.initialize()
        if self.gesture is None:
            if self.settings.protocol in {"demo-v0.3", "demo-v0.4"}:
                from app.demo_gesture import DemoGestureStateMachine
                gesture_class = "finger_gun" if self.settings.protocol == "demo-v0.4" else "help_gesture"
                camera_count=len(self.settings.camera_ids or (self.settings.camera_id,))
                max_gap=max(.75,1.5*camera_count/self.settings.max_fps)
                self.gesture = DemoGestureStateMachine(self.manager.engine.get_class_names().values(),
                    self.settings.enable_gesture,self.settings.gesture_conf,gesture_class,max_gap=max_gap)
            else:
                self.gesture = GestureStateMachine(self.manager.engine.get_class_names().values(), self.settings.enable_gesture,
                self.settings.gesture_window, self.settings.gesture_cooldown, self.settings.gesture_conf,
                self.settings.gesture_open, self.settings.gesture_fist)

    def get_model_metadata(self):
        self.load_model()
        info = self.manager.engine.get_model_info()
        if self.settings.model_version:
            info = {**info,"modelVersion":self.settings.model_version}
        return {**info, "gestureEnabled":self.gesture.enabled,
                "gestureValidation":"synthetic tests only; candidates are not confirmed emergencies"}

    def model_version(self):
        return self.get_model_metadata()["modelVersion"]

    def reset(self, camera_id=None):
        with self.lock:
            self.tracker.reset_tracking(camera_id)
            if self.gesture:
                if camera_id is not None and hasattr(self.gesture,"reset_camera"):
                    self.gesture.reset_camera(camera_id)
                else:
                    self.gesture.reset_state()
            if camera_id is None:
                self.contexts.clear(); self.last_captured.clear()
            else:
                self.contexts.pop(camera_id,None); self.last_captured.pop(camera_id,None)

    def expire_state(self, now):
        """Remove transient identities even when no more camera frames arrive."""
        with self.lock:
            for camera_id,captured in list(self.last_captured.items()):
                if now-captured > max(self.settings.track_retention,self.settings.gesture_cooldown):
                    self.reset(camera_id)

    def process_frame(self, frame):
        with self.lock:
            self.load_model()
            context = (frame.session_id,frame.generation,frame.camera_id)
            if context != self.contexts.get(frame.camera_id):
                self.reset(frame.camera_id)
                self.contexts[frame.camera_id] = context
            start = time.perf_counter()
            image = decode_jpeg(frame.jpeg,self.settings.max_pixels)
            if frame.width is not None and (frame.width,frame.height)!=(image.shape[1],image.shape[0]):
                raise ValueError("JPEG dimensions do not match header")
            decode_ms = (time.perf_counter()-start)*1000
            infer_start = time.perf_counter()
            detections = self.manager.infer_frame(image)
            inference_ms = (time.perf_counter()-infer_start)*1000
            allowed = {"person","head",self.settings.gesture_open,self.settings.gesture_fist}
            if self.settings.protocol in {"demo-v0.3", "demo-v0.4"}:
                allowed = {"person","head","help_gesture","finger_gun"}
            detections = [d for d in detections if d.class_name in allowed]
            if self.settings.enable_tracking:
                detections = self.tracker.update_tracks(frame.camera_id,detections,str(context),frame.timestamp_ms/1000)
            if self.settings.protocol in {"demo-v0.3", "demo-v0.4"}:
                from app.demo_gesture import associate_person_tracks
                detections = associate_person_tracks(detections)
            self.last_captured[frame.camera_id] = frame.timestamp_ms/1000
            stale = time.time()-frame.timestamp_ms/1000 > self.settings.max_frame_age
            model_version = self.model_version()
            events = self.gesture.process(frame.camera_id,detections,frame.timestamp_ms/1000,
                                          model_version,stale)
            if self.settings.log_result_summary:
                engine=self.manager.engine
                raw=engine.get_last_diagnostics() if hasattr(engine,"get_last_diagnostics") else {}
                gesture_debug=self.gesture.get_diagnostics(frame.camera_id) if hasattr(self.gesture,"get_diagnostics") else {}
                logging.getLogger(__name__).info("Inference debug cameraId=%s frameId=%s raw=%s tracked=%s gesture=%s",
                    frame.camera_id,frame.frame_id,raw,
                    [{"cls":d.class_name,"conf":round(d.confidence,4),"trackId":d.track_id} for d in detections],
                    gesture_debug)
            h,w = image.shape[:2]
            serialized = [{"classId":d.class_id,"className":d.class_name,"confidence":d.confidence,
                           "trackId":d.track_id,"bbox":normalize_bbox(d.bbox_xyxy,w,h)} for d in detections]
            result = build_detection_message(frame,serialized,model_version,inference_ms,events,self.manager.backend)
            result.update(build_count_result(frame.camera_id,detections))
            result["inferenceBackend"] = self.manager.backend
            return result,decode_ms,inference_ms,(time.perf_counter()-start)*1000

    def close(self):
        self.reset()
        self.manager.shutdown()
