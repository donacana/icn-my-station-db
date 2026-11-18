import cv2
import numpy as np
import pytest
from app.preprocessing import decode_jpeg,letterbox,restore_boxes,normalize_bbox


def test_letterbox_inverse_and_rgb():
    image=np.zeros((360,640,3),np.uint8); image[:]=[0,0,255]
    tensor,info=letterbox(image,(416,416))
    assert tensor.shape==(1,3,416,416) and tensor.dtype==np.float32
    assert tensor[0,0,208,208]==1 and tensor[0,2,208,208]==0
    box=np.array([[10,20,600,340]],np.float32)
    encoded=box*info.scale+np.array([*info.pad_xy,*info.pad_xy])
    np.testing.assert_allclose(restore_boxes(encoded,info),box,atol=1e-4)


def test_jpeg():
    _,data=cv2.imencode('.jpg',np.zeros((32,40,3),np.uint8))
    assert decode_jpeg(data.tobytes()).shape==(32,40,3)
    with pytest.raises(ValueError): decode_jpeg(data.tobytes(),100)


@pytest.mark.parametrize("data",[b"",b"notjpeg",b"\xff\xd8garbage\xff\xd9"])
def test_bad_jpeg(data):
    with pytest.raises(ValueError): decode_jpeg(data)


def test_normalization():
    assert normalize_bbox([-5,0,120,50],100,100)==[0,0,1,0.5]
    with pytest.raises(ValueError): normalize_bbox([5,0,2,1],100,100)
