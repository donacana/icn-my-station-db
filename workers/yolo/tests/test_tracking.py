from app.tracking import PersonTracker
from app.inference_base import Detection

D=Detection(7,"person",.95,(10,10,100,200))


def test_new_and_stable_ids():
    tracker=PersonTracker()
    tracker.update_tracks("a",[D],"s",1)
    second=tracker.update_tracks("a",[D],"s",1.3)
    third=tracker.update_tracks("a",[D],"s",1.6)
    assert second[0].track_id is not None and second[0].track_id==third[0].track_id


def test_camera_session_reset_and_expiration():
    tracker=PersonTracker(retention=1)
    tracker.update_tracks("a",[D],"s",1)
    tracker.update_tracks("a",[D],"s",1.3)
    assert tracker.get_active_tracks("a")
    assert tracker.update_tracks("a",[D],"new",1.6)[0].track_id is None
    tracker.update_tracks("b",[D],"new",1.7)
    assert len(tracker.states)==2
    assert tracker.get_active_tracks("a",3)==[]
    tracker.reset_tracking()
    assert tracker.get_tracking_status()["cameras"]==0


def test_occlusion_reassociation():
    tracker=PersonTracker(retention=2)
    tracker.update_tracks("a",[D],"s",1)
    tid=tracker.update_tracks("a",[D],"s",1.3)[0].track_id
    assert tracker.update_tracks("a",[],"s",1.6)==[]
    assert tracker.update_tracks("a",[D],"s",1.9)[0].track_id==tid


def test_expired_ids_not_reused_and_low_confidence_recovery():
    from dataclasses import replace
    tracker=PersonTracker(retention=1)
    tracker.update_tracks("a",[D],"s",1)
    tid=tracker.update_tracks("a",[D],"s",1.3)[0].track_id
    low=replace(D,confidence=.4)
    assert tracker.update_tracks("a",[low],"s",1.6)[0].track_id==tid
    tracker.update_tracks("a",[D],"s",4)
    assert tracker.update_tracks("a",[D],"s",4.3)[0].track_id!=tid


def test_person_above_configured_threshold_can_activate_track():
    from dataclasses import replace
    tracker=PersonTracker(confidence=.25)
    candidate=replace(D,confidence=.30)
    tracker.update_tracks("a",[candidate],"s",1)
    assert tracker.update_tracks("a",[candidate],"s",1.3)[0].track_id is not None
