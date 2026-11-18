"""YOLO DEMO v0.3/v0.4 binary frame and result adapter."""
import json
import math
import struct
import time
from datetime import datetime
from urllib.parse import urlencode
from app.protocol import Frame, MAX_JPEG

MAX_HEADER = 16*1024
MAX_DEMO_PACKET = 4+MAX_HEADER+MAX_JPEG


def validate_camera_id(value):
    if type(value) is not int or not 1 <= value <= 2**63-1:
        raise ValueError("cameraId must be a positive PostgreSQL bigint integer")


def parse_camera_id_setting(value):
    if not isinstance(value,str) or not value.isascii() or not value.isdecimal():
        raise ValueError("cameraId setting/query must contain decimal digits")
    result=int(value)
    validate_camera_id(result)
    return result


def validate_header(header: dict) -> None:
    if not isinstance(header,dict):
        raise ValueError("Frame header must be a JSON object")
    camera=header.get("cameraId")
    validate_camera_id(camera)
    for key,limit in (("frameId",2**32-1),("capturedAt",2**63-1),("width",8192),("height",8192)):
        if type(header.get(key)) is not int or not 1<=header[key]<=limit:
            raise ValueError("Invalid frame metadata")
    if header["width"]*header["height"]>8_294_400:
        raise ValueError("Frame dimensions exceed limit")
    if "cameraSessionId" in header and (not isinstance(header["cameraSessionId"],str) or not 1<=len(header["cameraSessionId"])<=128):
        raise ValueError("Invalid optional camera session")


def encode_demo_frame(frame: Frame, **extras) -> bytes:
    header={"cameraId":frame.camera_id,"frameId":frame.frame_id,"capturedAt":frame.timestamp_ms,
            "width":frame.width,"height":frame.height,**extras}
    if frame.source_session_id:
        header["cameraSessionId"]=frame.source_session_id
    validate_header(header)
    raw=json.dumps(header,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode()
    if len(raw)>MAX_HEADER or not 1<=len(frame.jpeg)<=MAX_JPEG:
        raise ValueError("Frame size exceeds limit")
    return struct.pack("!I",len(raw))+raw+frame.jpeg


def parse_demo_frame(data: bytes, session_id: str="") -> Frame:
    if not isinstance(data,bytes) or not 5<=len(data)<=MAX_DEMO_PACKET:
        raise ValueError("Invalid binary frame size")
    size=struct.unpack_from("!I",data)[0]
    if not 2<=size<=MAX_HEADER or 4+size>=len(data) or len(data)-4-size>MAX_JPEG:
        raise ValueError("Invalid JSON header length")
    try:
        header=json.loads(data[4:4+size].decode("utf-8"))
    except (UnicodeDecodeError,json.JSONDecodeError):
        raise ValueError("Invalid UTF-8/JSON header") from None
    validate_header(header)
    return Frame(header["cameraId"],header["frameId"],header["capturedAt"],data[4+size:],
                 session_id,time.monotonic(),0,header.get("cameraSessionId",""),header["width"],header["height"])


def validate_demo_result(result: dict) -> None:
    if not isinstance(result,dict) or result.get("type")!="result":
        raise ValueError("Expected v0.3 result")
    for key,limit in (("frameId",2**32-1),("capturedAt",2**63-1)):
        if type(result.get(key)) is not int or not 1<=result[key]<=limit:
            raise ValueError("Invalid result identity")
    validate_camera_id(result.get("cameraId"))
    if type(result.get("personCount")) is not int or result["personCount"]<0:
        raise ValueError("Invalid personCount")
    ms=result.get("inferMs")
    if not isinstance(ms,(int,float)) or not math.isfinite(ms) or ms<0:
        raise ValueError("Invalid inferMs")
    if not isinstance(result.get("detections"),list) or not isinstance(result.get("events"),list):
        raise ValueError("Missing arrays")
    for d in result["detections"]:
        if not isinstance(d,dict) or d.get("cls") not in {"person","head","help_gesture","finger_gun"}:
            raise ValueError("Unsupported detection class")
        box=d.get("box")
        if not isinstance(box,list) or len(box)!=4 or not all(isinstance(x,(float,int)) and math.isfinite(x) and 0<=x<=1 for x in box):
            raise ValueError("Invalid box")
        if box[0]>box[2] or box[1]>box[3]:
            raise ValueError("Inverted box")
        conf=d.get("conf")
        if not isinstance(conf,(int,float)) or not math.isfinite(conf) or not 0<=conf<=1:
            raise ValueError("Invalid confidence")
        if d.get("trackId") is not None and (type(d["trackId"]) is not int or d["trackId"]<0):
            raise ValueError("Invalid trackId")
    if result["personCount"] != sum(d["cls"]=="person" for d in result["detections"]):
        raise ValueError("Conservative person count mismatch")
    for event in result["events"]:
        try:
            valid=(event["eventType"] in {"HELP_GESTURE","FINGER_GUN"} and type(event["trackId"]) is int
                   and event["trackId"]>=0 and 0<=event["confidence"]<=1
                   and datetime.fromisoformat(event["detectedAt"]).utcoffset() is not None)
        except (KeyError,ValueError,TypeError):
            valid=False
        if not valid:
            raise ValueError("Invalid demo event")


class DemoProtocol:
    name="demo-v0.3"
    expects_ack=False

    def connection_url(self,url: str,token: str) -> str:
        return url+"?"+urlencode({"token":token})

    def registration(self,camera_id,session_id,model_info=None,worker_id="icn-windows-worker"):
        info=model_info or {}
        names=info.get("classes",{})
        values=names.values() if isinstance(names,dict) else names
        return json.dumps({"type":"hello","workerId":worker_id,
            "modelVersion":info.get("modelVersion","unknown"),
            "classes":[v for v in values if v in {"person","head","help_gesture","finger_gun"}]})

    def parse(self,data,session_id):
        return parse_demo_frame(data,session_id)

    def control(self,message):
        # v0.3 defines no worker camera control/ACK. Do not invent one.
        raise ValueError("Unexpected worker text frame under v0.3")

    def serialize(self,result):
        mapped={"type":"result","cameraId":result["cameraId"],"frameId":result["frameId"],
            "capturedAt":result["timestampMs"],"inferMs":result["inferenceMs"],"personCount":result["personCount"],
            "detections":[{"cls":d["className"],"conf":d["confidence"],"box":d["bbox"],"trackId":d["trackId"]}
                          for d in result["detections"]],"events":result["events"],
            "modelVersion":result["modelVersion"],"inferenceBackend":result["inferenceBackend"]}
        if "cameraSessionId" in result:
            mapped["cameraSessionId"]=result["cameraSessionId"]
        validate_demo_result(mapped)
        return json.dumps(mapped,allow_nan=False,separators=(",",":"))

    def error(self,frame,model_error=False):
        return json.dumps({"type":"error","frameId":frame.frame_id,
            "code":"MODEL_ERROR" if model_error else "BAD_FRAME",
            "message":"inference failed" if model_error else "decode failed"})

    def status(self,camera_id,status):
        return None  # Backend owns connection status; no undocumented worker message.
