import numpy as np
import pytest
from app.preprocessing import LetterboxInfo
from app.postprocessing import classwise_nms,postprocess

INFO=LetterboxInfo((100,100),(100,100),1,(0,0))


def test_classwise_nms():
    boxes=np.array([[0,0,10,10]]*3)
    assert classwise_nms(boxes,np.array([.9,.8,.7]),np.array([0,0,1])).tolist()==[0,2]


def test_raw_confidence_and_invalid_boxes():
    output=np.array([[[50,50,50,50],[50,50,50,50],[20,20,-1,20],[20,20,20,20],[.9,.8,.99,.1]]],np.float32)
    result=postprocess(output,{0:"person"},INFO,.35,.45,"raw_bcn")
    assert len(result)==1 and result[0].bbox_xyxy==(40,40,60,60)


def test_embedded_nms_not_repeated():
    rows=np.array([[[1,1,20,20,.9,0],[1,1,20,20,.8,0]]],np.float32)
    assert len(postprocess(rows,{0:"person"},INFO,.35,.45,"nms_bnc"))==2


def test_class_count_mismatch():
    with pytest.raises(ValueError): postprocess(np.zeros((1,84,10)),{0:"person"},INFO,.35,.45,"raw_bcn")


def test_invalid_nms_class():
    with pytest.raises(ValueError): postprocess(np.array([[[0,0,20,20,.9,4]]]),{0:"person"},INFO,.35,.45,"nms_bnc")


def test_person_can_use_lower_class_specific_threshold_without_lowering_gesture():
    output=np.zeros((1,6,2),np.float32)
    output[0,:4,:]=np.array([[50,75],[50,75],[20,20],[20,20]])
    output[0,4,:]=[.30,.10]  # person
    output[0,5,:]=[.10,.40]  # finger_gun remains below its threshold
    result=postprocess(output,{0:"person",1:"finger_gun"},INFO,{0:.25,1:.60},.45,"raw_bcn")
    assert [(d.class_name,round(d.confidence,2)) for d in result]==[("person",.30)]
