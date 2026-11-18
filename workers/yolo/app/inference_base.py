"""Backend-independent pixel-coordinate detections."""
import ast
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import yaml


@dataclass(frozen=True)
class Detection:
    class_id: int
    class_name: str
    confidence: float
    bbox_xyxy: tuple[float, float, float, float]
    track_id: int | None = None


def class_names(metadata_names, yaml_path: Path | None = None) -> dict[int, str]:
    """Cross-check YAML and metadata; never guess semantic aliases."""
    def parse(value):
        if isinstance(value, str):
            value = ast.literal_eval(value)
        if isinstance(value, list):
            value = dict(enumerate(value))
        if not isinstance(value, dict) or not value:
            raise ValueError("Missing class names; provide CLASS_MAP_PATH")
        result = {int(k): v for k, v in value.items()}
        if set(result) != set(range(len(result))) or any(not isinstance(v, str) or not v for v in result.values()):
            raise ValueError("Classes must be contiguous zero-based names")
        if len(set(result.values())) != len(result):
            raise ValueError("Duplicate class names")
        return result
    embedded = parse(metadata_names) if metadata_names else None
    external = None
    if yaml_path:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Invalid data.yaml")
        external = parse(data.get("names"))
        if "nc" in data and data["nc"] != len(external):
            raise ValueError("data.yaml nc mismatch")
    if embedded and external and embedded != external:
        raise ValueError("Model metadata and data.yaml mismatch")
    names = embedded or external
    if not names or "person" not in names.values():
        raise ValueError("Model requires exact person class; verify data.yaml")
    return names


class InferenceEngine(ABC):
    @abstractmethod
    def load_model(self) -> None: ...
    @abstractmethod
    def infer(self, frame: np.ndarray) -> list[Detection]: ...
    @abstractmethod
    def get_class_names(self) -> dict[int, str]: ...
    @abstractmethod
    def get_model_info(self) -> dict: ...
    @abstractmethod
    def close(self) -> None: ...
