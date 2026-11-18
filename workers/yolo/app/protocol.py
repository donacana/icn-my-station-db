"""Provisional LOCAL mock contract. Replace adapter after EC2 contract arrives.

ICN1 | uint16 version=1 | uint64 frameId | uint64 Unix milliseconds |
uint16 camera UTF-8 byte count | camera | uint32 JPEG bytes | JPEG.
All integers network byte order. Session is local connection UUID, not wire data.
"""
import json
import math
import struct
import time
from dataclasses import dataclass
from typing import Any

MAX_JPEG = 8 * 1024 * 1024
MAX_PACKET = MAX_JPEG + 156
HEADER = struct.Struct("!4sHQQH")


@dataclass(frozen=True)
class Frame:
    camera_id: str | int
    frame_id: int
    timestamp_ms: int
    jpeg: bytes
    session_id: str = ""
    received_at: float = 0.0
    generation: int = 0
    source_session_id: str = ""
    width: int | None = None
    height: int | None = None


def parse_frame_message(data: bytes, session_id: str = "") -> Frame:
    """Strict packet parser; never prints payloads."""
    if not isinstance(data, bytes) or not HEADER.size + 4 <= len(data) <= MAX_PACKET:
        raise ValueError("Invalid packet length/type")
    magic, version, frame_id, timestamp, size = HEADER.unpack_from(data)
    if magic != b"ICN1" or version != 1 or not 1 <= size <= 128:
        raise ValueError("Invalid packet header")
    end = HEADER.size + size
    if end + 4 > len(data):
        raise ValueError("Truncated camera header")
    try:
        camera = data[HEADER.size:end].decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("Invalid UTF-8 camera") from None
    length = struct.unpack_from("!I", data, end)[0]
    if not camera.isprintable() or not 1 <= length <= MAX_JPEG or end + 4 + length != len(data):
        raise ValueError("Invalid camera/JPEG size")
    return Frame(camera, frame_id, timestamp, data[end + 4:], session_id, time.monotonic())


def encode_frame(frame: Frame) -> bytes:
    camera = frame.camera_id.encode("utf-8")
    data = HEADER.pack(b"ICN1", 1, frame.frame_id, frame.timestamp_ms, len(camera))
    data += camera + struct.pack("!I", len(frame.jpeg)) + frame.jpeg
    parse_frame_message(data)
    return data


def validate_result_message(result: dict) -> None:
    """Validate output coordinates, counts, identities and finite values."""
    if result.get("type") != "detection" or not ((isinstance(result.get("cameraId"),str) and bool(result["cameraId"])) or (type(result.get("cameraId")) is int and 1<=result["cameraId"]<=2**63-1)):
        raise ValueError("Invalid result identity")
    for key in ("frameId", "personCount"):
        if type(result.get(key)) is not int or result[key] < 0:
            raise ValueError("Invalid result integer")
    if not isinstance(result.get("sessionId"), str) or not result["sessionId"] or not result.get("modelVersion"):
        raise ValueError("Missing result metadata")
    if not isinstance(result.get("inferenceMs"), (int, float)) or not math.isfinite(result["inferenceMs"]) or result["inferenceMs"] < 0:
        raise ValueError("Invalid inference time")
    if not isinstance(result.get("detections"), list) or not isinstance(result.get("events"), list):
        raise ValueError("Invalid result arrays")
    if result.get("inferenceBackend") not in {"onnx_cpu", "torch_cpu", "torch_cuda", "test"}:
        raise ValueError("Missing/invalid inference backend")
    if result.get("status") != "LIVE" or type(result.get("cameraGeneration")) is not int:
        raise ValueError("Missing detection status/generation")
    for det in result["detections"]:
        box = det.get("bbox", [])
        if len(box) != 4 or not all(isinstance(x, (int, float)) and math.isfinite(x) and 0 <= x <= 1 for x in box):
            raise ValueError("Invalid bbox")
        if box[0] > box[2] or box[1] > box[3]:
            raise ValueError("Inverted bbox")
        if type(det.get("classId")) is not int or det["classId"] < 0 or not isinstance(det.get("className"), str):
            raise ValueError("Invalid class")
        conf = det.get("confidence")
        if not isinstance(conf, (int, float)) or not math.isfinite(conf) or not 0 <= conf <= 1:
            raise ValueError("Invalid confidence")
        if det.get("trackId") is not None and (type(det["trackId"]) is not int or det["trackId"] < 0):
            raise ValueError("Invalid track ID")
    if result["personCount"] != sum(d["className"] == "person" for d in result["detections"]):
        raise ValueError("Person count mismatch")
    for event in result["events"]:
        if event.get("eventType") in {"HELP_GESTURE", "FINGER_GUN"}:
            from datetime import datetime
            try:
                stamp = datetime.fromisoformat(event["detectedAt"])
                valid = (stamp.utcoffset() is not None and type(event.get("trackId")) is int
                         and event["trackId"] >= 0 and 0 <= event["confidence"] <= 1)
            except (ValueError, TypeError, KeyError):
                valid = False
            if not valid:
                raise ValueError("Invalid DEMO gesture event")
            continue
        if (event.get("eventType") != "help_candidate" or event.get("confirmed") is not False
                or event.get("cameraId") != result["cameraId"] or not event.get("eventId")
                or not isinstance(event.get("confidence"), (int, float))
                or not 0 <= event["confidence"] <= 1
                or not isinstance(event.get("detectedAt"), (int, float))
                or not math.isfinite(event["detectedAt"])):
            raise ValueError("Invalid gesture candidate")


def build_detection_message(frame: Frame, detections: list[dict], model_version: str,
                            inference_ms: float, events: list | None = None, inference_backend: str = "test") -> dict:
    result = {"type": "detection", "cameraId": frame.camera_id, "frameId": frame.frame_id,
              "sessionId": frame.session_id, "timestampMs": frame.timestamp_ms,
              "cameraGeneration": frame.generation, "inferenceBackend": inference_backend, "status": "LIVE",
              "personCount": sum(d["className"] == "person" for d in detections),
              "countSource": "person", "modelVersion": model_version,
              "inferenceMs": inference_ms, "detections": detections, "events": events or []}
    if frame.source_session_id:
        result["cameraSessionId"] = frame.source_session_id
    validate_result_message(result)
    return result


def serialize_detection_result(result: dict) -> str:
    validate_result_message(result)
    return json.dumps(result, allow_nan=False, separators=(",", ":"))


class MockProtocol:
    """Replaceable adapter: registration, controls, binary and result encoding."""
    name = "mock-v1"

    def registration(self, camera_id: str, session_id: str, **kwargs) -> str:
        return json.dumps({"type": "register", "protocol": self.name,
                           "cameraId": camera_id, "sessionId": session_id})

    def check_ack(self, message: str | bytes) -> None:
        if not isinstance(message, str) or json.loads(message) != {"type": "registered", "protocol": self.name}:
            raise ValueError("Mock registration rejected")

    def parse(self, message: bytes, session_id: str) -> Frame:
        return parse_frame_message(message, session_id)

    def control(self, message: str) -> dict[str, Any]:
        value = json.loads(message)
        if not isinstance(value, dict) or value.get("type") not in {"camera_offline", "camera_session"} or not isinstance(value.get("cameraId"), str):
            raise ValueError("Unknown mock control")
        if value["type"] == "camera_session" and (not isinstance(value.get("sessionId"), str) or not value["sessionId"]):
            raise ValueError("Missing camera session ID")
        return value

    def serialize(self, result: dict) -> str:
        return serialize_detection_result(result)

    def status(self, camera_id: str, status: str) -> str:
        if status not in {"STALE", "OFFLINE"}:
            raise ValueError("Invalid camera status")
        return json.dumps({"type": "camera_status", "cameraId": camera_id, "status": status, "personCount": None})


validate_detection_result = validate_result_message


def validate_frame_metadata(frame: Frame) -> None:
    if not frame.camera_id or type(frame.frame_id) is not int or not 0 <= frame.frame_id < 2**64:
        raise ValueError("Invalid frame identity")
    if type(frame.timestamp_ms) is not int or not 0 < frame.timestamp_ms < 2**64:
        raise ValueError("Invalid capturedAt milliseconds")
