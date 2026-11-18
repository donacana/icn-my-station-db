from app.inference_base import Detection
from app.counting import count_visible_persons,count_tracked_persons,build_count_result,calculate_visible_count,match_heads_to_persons


def test_current_counts_and_dedupe():
    p=Detection(3,"person",.9,(0,0,10,10),1)
    h=Detection(0,"head",.9,(0,0,1,1))
    assert count_visible_persons([])==0
    assert count_visible_persons([p,h])==1
    assert count_visible_persons([p,p,h])==2
    assert count_tracked_persons([p,p])==1
    assert build_count_result("a",[p],"OFFLINE")["personCount"] is None
    assert build_count_result("a",[],"STALE")["status"]=="STALE"


def test_head_not_automatically_added():
    assert calculate_visible_count([1],[2,3])==1
    assert len(match_heads_to_persons([[0,0,100,200]],[[10,10,20,20],[30,10,40,20]]))==1
