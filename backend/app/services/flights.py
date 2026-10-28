"""운항 현황 mock. DB가 준비되면 이 모듈 안에서만 쿼리로 교체한다."""

from datetime import timedelta

from app.core import rules
from app.core.timeutil import now_kst
from app.schemas import Direction, Flight, Terminal


class FlightNotFoundError(Exception):
    def __init__(self, flight_no: str):
        super().__init__(f"편명 {flight_no}을(를) 찾을 수 없습니다.")
        self.flight_no = flight_no


# (편명, 항공사, 방향, 도시, 공항코드, 예정 시각 오프셋(분), 지연(분), 터미널, 게이트, 원본 상태)
_MOCK_ROWS: list[tuple] = [
    (
        "KE703",
        "대한항공",
        Direction.DEPARTURE,
        "도쿄(나리타)",
        "NRT",
        -10,
        0,
        Terminal.T1,
        248,
        "탑승중",
    ),
    (
        "OZ102",
        "아시아나항공",
        Direction.DEPARTURE,
        "도쿄(하네다)",
        "HND",
        15,
        0,
        Terminal.T1,
        112,
        "탑승준비",
    ),
    (
        "KE671",
        "대한항공",
        Direction.DEPARTURE,
        "오사카(간사이)",
        "KIX",
        30,
        25,
        Terminal.T2,
        255,
        "예정",
    ),
    ("DL158", "델타항공", Direction.DEPARTURE, "시애틀", "SEA", 45, 0, Terminal.T2, 266, "예정"),
    ("7C1101", "제주항공", Direction.DEPARTURE, "방콕", "BKK", 60, 0, Terminal.T1, 30, "예정"),
    ("KE901", "대한항공", Direction.DEPARTURE, "뉴욕(JFK)", "JFK", 80, 0, Terminal.T2, 250, "예정"),
    ("AF267", "에어프랑스", Direction.DEPARTURE, "파리", "CDG", 95, 0, Terminal.T2, None, "예정"),
    (
        "TW202",
        "티웨이항공",
        Direction.DEPARTURE,
        "후쿠오카",
        "FUK",
        -40,
        0,
        Terminal.T1,
        18,
        "출발",
    ),
    (
        "KE706",
        "대한항공",
        Direction.ARRIVAL,
        "도쿄(나리타)",
        "NRT",
        -5,
        0,
        Terminal.T2,
        None,
        "도착",
    ),
    (
        "OZ101",
        "아시아나항공",
        Direction.ARRIVAL,
        "도쿄(하네다)",
        "HND",
        10,
        0,
        Terminal.T1,
        None,
        "예정",
    ),
    (
        "KE672",
        "대한항공",
        Direction.ARRIVAL,
        "오사카(간사이)",
        "KIX",
        25,
        20,
        Terminal.T2,
        None,
        "예정",
    ),
    ("DL159", "델타항공", Direction.ARRIVAL, "시애틀", "SEA", 40, 0, Terminal.T2, None, "예정"),
    ("7C1102", "제주항공", Direction.ARRIVAL, "방콕", "BKK", 55, 0, Terminal.T1, None, "예정"),
    ("KE902", "대한항공", Direction.ARRIVAL, "뉴욕(JFK)", "JFK", 70, 0, Terminal.T2, None, "예정"),
    ("AF268", "에어프랑스", Direction.ARRIVAL, "파리", "CDG", 90, 0, Terminal.T2, None, "회항"),
    (
        "TW201",
        "티웨이항공",
        Direction.ARRIVAL,
        "후쿠오카",
        "FUK",
        -30,
        0,
        Terminal.T1,
        None,
        "도착",
    ),
]


def _normalize(flight_no: str | None) -> str | None:
    if flight_no is None:
        return None
    return flight_no.strip().upper() or None


def ensure_flight_exists(flight_no: str | None) -> str | None:
    """flightNo가 주어졌는데 없는 편명이면 FlightNotFoundError. 정규화된 편명을 돌려준다."""
    normalized = _normalize(flight_no)
    if normalized is not None and all(row[0] != normalized for row in _MOCK_ROWS):
        raise FlightNotFoundError(normalized)
    return normalized


def list_flights(direction: Direction, flight_no: str | None = None) -> list[Flight]:
    my_flight_no = ensure_flight_exists(flight_no)
    base = now_kst().replace(minute=0, second=0)
    flights: list[Flight] = []
    for no, airline, kind, city, code, offset, delay, terminal, gate, raw_status in _MOCK_ROWS:
        if kind != direction:
            continue
        scheduled = base + timedelta(minutes=offset)
        flights.append(
            Flight(
                flight_no=no,
                airline=airline,
                type=kind,
                city=city,
                airport_code=code,
                scheduled_at=scheduled,
                estimated_at=scheduled + timedelta(minutes=delay) if delay else None,
                terminal=terminal,
                gate=gate,
                status=rules.resolve_status(raw_status, delay),
                delay_minutes=delay,
                is_my_flight=no == my_flight_no,
            )
        )
    return sorted(flights, key=lambda f: f.scheduled_at)
