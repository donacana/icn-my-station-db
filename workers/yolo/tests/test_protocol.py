import json
import pytest
from app.protocol import Frame,encode_frame,parse_frame_message,build_detection_message,serialize_detection_result,validate_result_message


def test_packet_roundtrip():
    f=Frame("카메라",2**40,12345,b"jpeg")
    out=parse_frame_message(encode_frame(f),"session")
    assert (out.camera_id,out.frame_id,out.timestamp_ms,out.jpeg)==(f.camera_id,f.frame_id,f.timestamp_ms,f.jpeg)


@pytest.mark.parametrize("data",[b"",b"ICN1",b"x"*100,"text"])
def test_invalid_packet(data):
    with pytest.raises(ValueError): parse_frame_message(data)


def test_length_corruption():
    packet=encode_frame(Frame("c",1,1,b"jpeg"))
    for bad in [packet[:-1],packet+b"x",b"BAD!"+packet[4:]]:
        with pytest.raises(ValueError): parse_frame_message(bad)


def test_json_validation():
    result=build_detection_message(Frame("c",1,1,b"","s"),[],"m",1)
    assert json.loads(serialize_detection_result(result))["personCount"]==0
    result["inferenceMs"]=float("nan")
    with pytest.raises(ValueError): validate_result_message(result)
