"""Bounded JPEG decoding and invertible YOLO letterbox transform."""
import io
from dataclasses import dataclass
import cv2
import numpy as np
from PIL import Image
from app.protocol import MAX_JPEG


@dataclass(frozen=True)
class LetterboxInfo:
    original_hw: tuple[int, int]
    input_hw: tuple[int, int]
    scale: float
    pad_xy: tuple[int, int]


def decode_jpeg(data: bytes, max_pixels: int = 8_294_400) -> np.ndarray:
    if not data or len(data) > MAX_JPEG or not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
        raise ValueError("Empty, oversized or truncated JPEG")
    try:
        with Image.open(io.BytesIO(data)) as header:
            width, height = header.size
            if header.format != "JPEG" or width * height > max_pixels or min(width, height) < 16:
                raise ValueError("JPEG dimensions outside limits")
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
    except Exception:
        raise ValueError("Invalid JPEG") from None
    if image is None or image.shape[:2] != (height, width):
        raise ValueError("JPEG decode failed")
    return image


def letterbox(image: np.ndarray, input_hw: tuple[int, int]) -> tuple[np.ndarray, LetterboxInfo]:
    if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8 or min(image.shape[:2]) < 1:
        raise ValueError("Expected nonempty uint8 BGR image")
    h, w = image.shape[:2]
    th, tw = input_hw
    if min(th, tw) < 32 or max(th, tw) > 1920:
        raise ValueError("Unsupported input dimensions")
    scale = min(th / h, tw / w)
    nw, nh = round(w * scale), round(h * scale)
    left, top = (tw - nw) // 2, (th - nh) // 2
    resized = cv2.resize(image, (nw, nh), interpolation=cv2.INTER_LINEAR)
    padded = cv2.copyMakeBorder(resized, top, th - nh - top, left, tw - nw - left,
                                cv2.BORDER_CONSTANT, value=(114, 114, 114))
    tensor = np.ascontiguousarray(padded[:, :, ::-1].transpose(2, 0, 1)[None], dtype=np.float32) / 255.0
    return tensor, LetterboxInfo((h, w), input_hw, scale, (left, top))


def restore_boxes(boxes: np.ndarray, info: LetterboxInfo) -> np.ndarray:
    boxes = np.asarray(boxes, dtype=np.float32).copy().reshape(-1, 4)
    boxes[:, [0, 2]] = (boxes[:, [0, 2]] - info.pad_xy[0]) / info.scale
    boxes[:, [1, 3]] = (boxes[:, [1, 3]] - info.pad_xy[1]) / info.scale
    boxes[:, [0, 2]] = np.clip(boxes[:, [0, 2]], 0, info.original_hw[1])
    boxes[:, [1, 3]] = np.clip(boxes[:, [1, 3]], 0, info.original_hw[0])
    return boxes


def normalize_bbox(box, width: int, height: int) -> list[float]:
    values = np.asarray(box, dtype=float)
    if values.shape != (4,) or not np.isfinite(values).all() or min(width, height) <= 0:
        raise ValueError("Invalid bounding box")
    if values[0] > values[2] or values[1] > values[3]:
        raise ValueError("Inverted bounding box")
    return np.clip(values / [width, height, width, height], 0, 1).tolist()
