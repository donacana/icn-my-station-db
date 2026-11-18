"""v0.3 continuous help_gesture, independent of legacy open/fist sequence."""
from dataclasses import replace
from datetime import datetime, timezone, timedelta


def associate_person_tracks(detections):
    persons = [d for d in detections if d.class_name == "person"]
    assignments = {}
    for i, d in enumerate(detections):
        if d.class_name not in {"head", "help_gesture", "finger_gun"}:
            continue
        x, y = (d.bbox_xyxy[0]+d.bbox_xyxy[2])/2, (d.bbox_xyxy[1]+d.bbox_xyxy[3])/2
        matches = []
        for p in persons:
            x1,y1,x2,y2 = p.bbox_xyxy
            bottom = y1+.4*(y2-y1) if d.class_name == "head" else y2
            if p.track_id is not None and x1<=x<=x2 and y1<=y<=bottom:
                matches.append(p.track_id)
        if len(matches)==1:
            assignments[i] = matches[0]
    # Two candidate hands/heads for one person are ambiguous: do not claim identity.
    result = []
    for i,d in enumerate(detections):
        if d.class_name in {"head","help_gesture","finger_gun"}:
            track_id = assignments.get(i)
            peers = sum(detections[j].class_name==d.class_name and t==track_id
                        for j,t in assignments.items())
            d = replace(d,track_id=track_id if peers==1 else None)
        result.append(d)
    return result


class DemoGestureStateMachine:
    def __init__(self, names, enabled=True, confidence=.6, gesture_class="help_gesture",max_gap=.75):
        self.gesture_class = gesture_class
        self.event_type = "FINGER_GUN" if gesture_class == "finger_gun" else "HELP_GESTURE"
        self.enabled = enabled and gesture_class in names
        self.confidence = confidence
        self.max_gap = max_gap
        self.reset_state()

    def reset_state(self):
        self.progress = {}
        self.cooldowns = {}
        self.last_timestamp = {}
        self.diagnostics = {}

    def reset_camera(self, camera_id):
        self.progress = {k:v for k,v in self.progress.items() if k[0] != camera_id}
        self.cooldowns = {k:v for k,v in self.cooldowns.items() if k[0] != camera_id}
        self.last_timestamp.pop(camera_id, None)
        self.diagnostics.pop(camera_id,None)

    def process(self, camera_id, detections, timestamp, model_version, stale=False):
        if not self.enabled:
            self.diagnostics[camera_id]={"reason":"disabled"}
            return []
        previous = self.last_timestamp.get(camera_id)
        if stale or (previous is not None and timestamp<=previous):
            self.reset_camera(camera_id)
            self.diagnostics[camera_id]={"reason":"stale_or_non_monotonic"}
            return []
        self.last_timestamp[camera_id] = timestamp
        self.cooldowns = {k:v for k,v in self.cooldowns.items() if timestamp-v<10}
        present = {}
        for d in detections:
            if d.class_name==self.gesture_class and d.track_id is not None and d.confidence>=self.confidence:
                present[(camera_id,d.track_id)] = d.confidence
        self.progress = {k:v for k,v in self.progress.items() if k[0] != camera_id or k in present}
        events = []
        for key,conf in present.items():
            start,last,minimum = self.progress.get(key,(timestamp,timestamp,conf))
            if timestamp-last>self.max_gap:
                start,minimum = timestamp,conf
            minimum = min(minimum,conf)
            self.progress[key] = (start,timestamp,minimum)
            if timestamp-start>=1.5 and key not in self.cooldowns:
                events.append({"eventType":self.event_type,"trackId":key[1],"confidence":minimum,
                    "detectedAt":datetime.fromtimestamp(timestamp,timezone(timedelta(hours=9))).isoformat(timespec="milliseconds")})
                self.cooldowns[key] = timestamp
        linked=len(present)
        elapsed=max((timestamp-v[0] for k,v in self.progress.items() if k[0]==camera_id),default=0.0)
        cooldown=max((10-(timestamp-v) for k,v in self.cooldowns.items() if k[0]==camera_id),default=0.0)
        self.diagnostics[camera_id]={"reason":"event_created" if events else
            ("no_linked_finger_gun" if not linked else "cooldown" if cooldown>0 else "waiting_1.5_seconds"),
            "linkedCandidates":linked,"continuousSeconds":round(elapsed,3),"cooldownRemaining":round(max(0,cooldown),3),
            "maxGapSeconds":round(self.max_gap,3)}
        return events

    def get_diagnostics(self,camera_id):
        return dict(self.diagnostics.get(camera_id,{}))
