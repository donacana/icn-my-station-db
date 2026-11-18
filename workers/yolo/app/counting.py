"""Current visible counts, never cumulative traffic."""


def count_persons(detections: list[dict]) -> int:
    return sum(d["className"] == "person" for d in detections)


def match_heads_to_persons(person_boxes: list, head_boxes: list, upper_ratio: float = 0.4) -> list[tuple[int, int]]:
    """Maximum one-to-one matching of head centers in upper person regions."""
    if not 0 < upper_ratio <= 1:
        raise ValueError("Invalid upper-body ratio")
    candidates = []
    for head in head_boxes:
        cx, cy = (head[0] + head[2]) / 2, (head[1] + head[3]) / 2
        candidates.append([i for i, p in enumerate(person_boxes)
                           if p[0] <= cx <= p[2] and p[1] <= cy <= p[1] + upper_ratio * (p[3] - p[1])])
    assigned: dict[int, int] = {}
    def assign(h: int, seen: set[int]) -> bool:
        for p in candidates[h]:
            if p not in seen:
                seen.add(p)
                if p not in assigned or assign(assigned[p], seen):
                    assigned[p] = h
                    return True
        return False
    for h in range(len(head_boxes)):
        assign(h, set())
    return sorted((p, h) for p, h in assigned.items())


def calculate_visible_count(persons: list, heads: list, *, add_unmatched_heads: bool = False,
                            upper_ratio: float = 0.4) -> int:
    if not add_unmatched_heads:
        return len(persons)
    return len(persons) + len(heads) - len(match_heads_to_persons(persons, heads, upper_ratio))


def count_visible_persons(detections):
    """Count current detections, even before a track becomes confirmed."""
    return sum(d.class_name == "person" for d in detections)

def count_tracked_persons(detections):
    return len({d.track_id for d in detections if d.class_name == "person" and d.track_id is not None})

def build_count_result(camera_id, detections, status="LIVE"):
    if status not in {"LIVE", "STALE", "OFFLINE"}:
        raise ValueError("Unknown camera status")
    return {"cameraId":camera_id, "personCount":count_visible_persons(detections) if status == "LIVE" else None,
            "countSource":"person", "status":status}
