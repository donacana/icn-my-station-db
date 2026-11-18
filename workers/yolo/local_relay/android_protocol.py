"""Read-only Android compatibility: ICN1 (24-byte prefix), raw JPEG, native v0.3."""
import io
import time
from dataclasses import replace
from PIL import Image
from app.protocol import Frame, MAX_JPEG, parse_frame_message, validate_frame_metadata
from app.demo_protocol import parse_demo_frame, parse_camera_id_setting


def camera_identity(header, query, expected):
    values = [v for v in (header,query) if v is not None]
    if not values or any(parse_camera_id_setting(v)!=expected for v in values):
        raise ValueError("Camera identity missing or mismatched")
    return expected


def parse_android_frame(data, camera_id, raw_sequence, now_ms=None):
    now_ms = int(time.time()*1000) if now_ms is None else now_ms
    if not isinstance(data,bytes):
        raise ValueError("Binary frame required")
    if data.startswith(b"ICN1"):
        frame = parse_frame_message(data)
        if frame.frame_id>=2**63 or frame.timestamp_ms>=2**63:
            raise ValueError("Negative Android signed Long")
        frame = replace(frame,camera_id=parse_camera_id_setting(frame.camera_id))
        mode = "ICN1"
    elif data.startswith(b"\xff\xd8"):
        frame = Frame(camera_id,raw_sequence,now_ms,data)
        mode = "RAW_JPEG"
    else:
        frame = parse_demo_frame(data)
        mode = "demo-v0.3"
    validate_frame_metadata(frame)
    if frame.camera_id!=camera_id:
        raise ValueError("Camera mismatch")
    if not 4<=len(frame.jpeg)<=MAX_JPEG or not frame.jpeg.startswith(b"\xff\xd8") or not frame.jpeg.endswith(b"\xff\xd9"):
        raise ValueError("Invalid JPEG framing")
    try:
        with Image.open(io.BytesIO(frame.jpeg)) as image:
            width,height = image.size
            if image.format!="JPEG" or width*height>8_294_400 or max(width,height)>8192:
                raise ValueError("Invalid image dimensions")
    except (OSError,Image.DecompressionBombError):
        raise ValueError("Invalid JPEG header") from None
    if frame.width is not None and (frame.width,frame.height)!=(width,height):
        raise ValueError("JPEG/header dimension mismatch")
    return replace(frame,width=width,height=height),mode
