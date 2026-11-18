"""Conservative spatially associated help candidates, never emergency confirmation."""
import math
import uuid

class GestureStateMachine:
    def __init__(self, classes=(), enabled=True, window=2.0, cooldown=30.0,
                 confidence=0.6, open_class="help_open", fist_class="help_fist"):
        self.enabled = enabled and {open_class, fist_class}.issubset(classes)
        self.window, self.cooldown, self.confidence = window, cooldown, confidence
        self.open_class, self.fist_class = open_class, fist_class
        self.opened, self.last_event, self.last_seen, self.hands = {}, {}, {}, {}

    def apply_cooldown(self, key, timestamp):
        return timestamp - self.last_event.get(key, float("-inf")) >= self.cooldown

    def update(self, camera_id, track_id, gesture_class, timestamp, *, verified_hand=False,
               confidence=0.0, model_version="unknown", stale=False, cooldown_key=None):
        if not self.enabled or not verified_hand or not track_id or stale:
            return None
        if not math.isfinite(timestamp) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("Invalid gesture evidence")
        if confidence < self.confidence:
            return None
        key = (camera_id, track_id)
        if timestamp <= self.last_seen.get(key, float("-inf")):
            self.opened.pop(key, None)
            return None
        self.last_seen[key] = timestamp
        for old, seen in list(self.last_seen.items()):
            if timestamp - seen > max(self.window, self.cooldown):
                self.opened.pop(old, None)
                self.last_seen.pop(old, None)
        for old, event_time in list(self.last_event.items()):
            if timestamp - event_time > self.cooldown:
                self.last_event.pop(old, None)
        if gesture_class == self.open_class:
            self.opened[key] = (timestamp, confidence)
            return None
        opened = self.opened.pop(key, None)
        dedupe = (camera_id, cooldown_key or track_id)
        if gesture_class == self.fist_class and opened and 0 < timestamp - opened[0] <= self.window and self.apply_cooldown(dedupe, timestamp):
            self.last_event[dedupe] = timestamp
            return {"cameraId": camera_id, "eventType": "help_candidate", "confidence": min(confidence, opened[1]),
                    "detectedAt": timestamp, "modelVersion": model_version, "eventId": str(uuid.uuid4()),
                    "association": "conservative_spatial", "confirmed": False}
        return None

    def match_gesture_target(self, camera_id, detections, timestamp):
        """Require unique containing person and one gesture per person, small motion.

        Hand identities are independently generated, never copied from person IDs.
        Ambiguous/multiple hands invalidate that person's pending sequence.
        """
        persons = [d for d in detections if d.class_name == "person" and d.track_id is not None]
        gestures = [d for d in detections if d.class_name in {self.open_class,self.fist_class} and d.confidence >= self.confidence]
        groups = {}
        ambiguous = set()
        for hand in gestures:
            x1,y1,x2,y2 = hand.bbox_xyxy
            cx,cy = (x1+x2)/2,(y1+y2)/2
            candidates = [p for p in persons if p.bbox_xyxy[0] <= cx <= p.bbox_xyxy[2] and p.bbox_xyxy[1] <= cy <= p.bbox_xyxy[3]]
            if len(candidates) != 1:
                ambiguous.update(p.track_id for p in candidates)
                continue
            person = candidates[0]
            groups.setdefault(person.track_id, []).append((hand,person,cx,cy))
        matches = []
        for key, hand in list(self.hands.items()):
            if timestamp - hand["time"] > min(self.window,1.0):
                self.opened.pop((key[0],hand["id"]),None)
                self.hands.pop(key,None)
        for pid, group in groups.items():
            key = (camera_id,pid)
            previous = self.hands.get(key)
            if len(group) != 1 or pid in ambiguous:
                if previous:
                    self.opened.pop((camera_id,previous["id"]),None)
                    self.hands.pop(key,None)
                continue
            hand,person,cx,cy = group[0]
            px1,py1,px2,py2 = person.bbox_xyxy
            area = (hand.bbox_xyxy[2]-hand.bbox_xyxy[0])*(hand.bbox_xyxy[3]-hand.bbox_xyxy[1])
            diag = math.hypot(px2-px1,py2-py1)
            same = previous and 0 < timestamp-previous["time"] <= 1.0 and math.hypot(cx-previous["cx"],cy-previous["cy"]) <= 0.08*diag and 0.4 <= area/max(previous["area"],1e-9) <= 2.5
            if previous and not same:
                self.opened.pop((camera_id,previous["id"]),None)
            hid = previous["id"] if same else str(uuid.uuid4())
            self.hands[key] = {"id":hid,"time":timestamp,"cx":cx,"cy":cy,"area":area}
            matches.append((hid,pid,hand))
        for pid in ambiguous:
            previous = self.hands.pop((camera_id,pid),None)
            if previous:
                self.opened.pop((camera_id,previous["id"]),None)
        return matches

    def process(self, camera_id, detections, timestamp, model_version, stale=False):
        if not self.enabled or stale:
            return []
        events = []
        for hid,pid,hand in self.match_gesture_target(camera_id,detections,timestamp):
            event = self.update(camera_id,hid,hand.class_name,timestamp,verified_hand=True,
                confidence=hand.confidence,model_version=model_version,stale=stale,cooldown_key=str(pid))
            if event:
                events.append(event)
        return events

    def detect_help_sequence(self,*args,**kwargs):
        return self.update(*args,**kwargs)

    def reset_state(self):
        self.opened.clear()
        self.last_event.clear()
        self.last_seen.clear()
        self.hands.clear()

    reset_gesture_state = reset_state
