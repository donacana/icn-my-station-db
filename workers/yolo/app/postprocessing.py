"""Explicit supported YOLO11 Detect outputs; unknown layouts fail closed."""
import numpy as np
from app.inference_base import Detection
from app.preprocessing import LetterboxInfo, restore_boxes


def classwise_nms(boxes, scores, classes, iou_threshold=0.45, max_det=300):
    """Greedy per-class IoU NMS, bounded candidate set."""
    order = np.argsort(-scores, kind="stable")[:30000]
    keep = []
    areas = np.maximum(0, boxes[:, 2] - boxes[:, 0]) * np.maximum(0, boxes[:, 3] - boxes[:, 1])
    while len(order) and len(keep) < max_det:
        i = order[0]
        keep.append(int(i))
        rest = order[1:]
        xy1 = np.maximum(boxes[i, :2], boxes[rest, :2])
        xy2 = np.minimum(boxes[i, 2:], boxes[rest, 2:])
        intersect = np.prod(np.maximum(0, xy2 - xy1), axis=1)
        iou = intersect / np.maximum(areas[i] + areas[rest] - intersect, 1e-9)
        order = rest[(classes[rest] != classes[i]) | (iou <= iou_threshold)]
    return np.asarray(keep, dtype=int)


def postprocess(output: np.ndarray, names: dict[int, str], info: LetterboxInfo,
                conf: float | dict[int,float], iou: float, layout: str) -> list[Detection]:
    if output.ndim != 3 or output.shape[0] != 1:
        raise ValueError("Unsupported ONNX output rank/batch")
    if layout == "raw_bcn":
        if output.shape[1] != 4 + len(names):
            raise ValueError("Class count/output channels mismatch")
        rows = output[0].T
        cls = rows[:, 4:].argmax(axis=1)
        scores = rows[np.arange(len(rows)), cls + 4]
        boxes = np.column_stack((rows[:, :2] - rows[:, 2:4] / 2, rows[:, :2] + rows[:, 2:4] / 2))
    elif layout == "nms_bnc":
        if output.shape[2] != 6:
            raise ValueError("Embedded NMS output must be [1,N,6]")
        rows = output[0]
        boxes, scores = rows[:, :4], rows[:, 4]
        raw_cls = rows[:, 5]
        if not np.isfinite(raw_cls).all() or np.any(raw_cls != np.floor(raw_cls)) or np.any((raw_cls < 0) | (raw_cls >= len(names))):
            raise ValueError("Invalid embedded NMS class IDs")
        cls = raw_cls.astype(int)
    else:
        raise ValueError("Unsupported ONNX layout")
    thresholds = (np.asarray([conf.get(int(c), min(conf.values())) for c in cls])
                  if isinstance(conf,dict) else conf)
    valid = (np.isfinite(boxes).all(axis=1) & np.isfinite(scores) & (scores >= thresholds) & (scores <= 1)
             & (boxes[:, 2] > boxes[:, 0]) & (boxes[:, 3] > boxes[:, 1]))
    boxes, scores, cls = boxes[valid], scores[valid], cls[valid]
    if layout == "raw_bcn":
        keep = classwise_nms(boxes, scores, cls, iou)
        boxes, scores, cls = boxes[keep], scores[keep], cls[keep]
    boxes = restore_boxes(boxes, info)
    return [Detection(int(c), names[int(c)], float(s), tuple(map(float, b)))
            for b, s, c in zip(boxes, scores, cls) if b[2] > b[0] and b[3] > b[1]]
