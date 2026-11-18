from app.gesture import GestureStateMachine
from app.inference_base import Detection


def machine(): return GestureStateMachine(["person","help_open","help_fist"])
def update(g,cls,t,hand="h",**kw): return g.update("cam",hand,cls,t,verified_hand=True,confidence=.9,**kw)


def test_sequence_cooldown_and_reset():
    g=machine()
    assert update(g,"help_open",1) is None
    assert update(g,"help_fist",2)["confirmed"] is False
    update(g,"help_open",3)
    assert update(g,"help_fist",4) is None
    update(g,"help_open",33)
    assert update(g,"help_fist",34)
    g.reset_state()
    assert update(g,"help_fist",35) is None


def test_reverse_timeout_other_hand_and_stale():
    g=machine()
    assert update(g,"help_fist",1) is None
    update(g,"help_open",2)
    assert update(g,"help_fist",5) is None
    update(g,"help_open",6)
    assert update(g,"help_fist",7,hand="other") is None
    assert update(g,"help_fist",7,stale=True) is None


def test_reversal_confidence_missing_classes():
    g=machine(); update(g,"help_open",2)
    assert update(g,"help_fist",1) is None
    assert update(g,"help_fist",2.5) is None
    assert not GestureStateMachine(["person"]).enabled
    assert g.update("cam","h","help_open",3,verified_hand=True,confidence=.1) is None
    assert g.update("cam","person-id","help_fist",4,confidence=.9) is None


def test_spatial_association_and_ambiguity():
    p=Detection(0,"person",.9,(0,0,100,200),10)
    op=Detection(1,"help_open",.9,(40,40,50,50))
    fi=Detection(2,"help_fist",.9,(41,41,51,51))
    far=Detection(2,"help_fist",.9,(80,140,90,150))
    g=machine()
    assert g.process("cam",[p,op],1,"demo")==[]
    assert len(g.process("cam",[p,fi],1.3,"demo"))==1
    g.reset_state(); g.process("cam",[p,op],2,"demo")
    assert g.process("cam",[p,far],2.3,"demo")==[]
    g.reset_state(); g.process("cam",[p,op],3,"demo")
    assert g.process("cam",[p,fi,far],3.3,"demo")==[]
