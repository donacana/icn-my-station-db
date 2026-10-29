"""백엔드가 관리하는 업무 기준값. 운항 상태 매핑, 지연 기준, 점수 공식, 혼잡 단계 기준."""

from app.schemas import CongestionLevel, FlightStatus, OperationLevel

# 지연 기준(분)
DELAY_THRESHOLD_MINUTES = 15

# 메인 요약의 출발/도착 최대 건수
SUMMARY_FLIGHT_LIMIT = 6

# 운항 상태 매핑: 원본 상태 -> 표준 코드
STATUS_MAP: dict[str, FlightStatus] = {
    "예정": FlightStatus.SCHEDULED,
    "탑승준비": FlightStatus.BOARDING_SOON,
    "탑승중": FlightStatus.BOARDING,
    "지연": FlightStatus.DELAYED,
    "결항": FlightStatus.CANCELLED,
    "출발": FlightStatus.DEPARTED,
    "도착": FlightStatus.ARRIVED,
    "회항": FlightStatus.DIVERTED,
}


def resolve_status(raw_status: str, delay_minutes: int) -> FlightStatus:
    """원본 상태를 표준 코드로 바꾼다. 예정/탑승준비 상태라도 지연 기준을 넘으면 DELAYED."""
    code = STATUS_MAP.get(raw_status, FlightStatus.SCHEDULED)
    if (
        code in (FlightStatus.SCHEDULED, FlightStatus.BOARDING_SOON)
        and delay_minutes >= DELAY_THRESHOLD_MINUTES
    ):
        return FlightStatus.DELAYED
    return code


# 혼잡 단계 기준(대기 인원, 명). 임시값이며 실제 데이터 기준이 정해지면 교체한다.
CONGESTION_MID_FROM = 200
CONGESTION_HIGH_FROM = 400


def congestion_level(waiting_count: int) -> CongestionLevel:
    if waiting_count >= CONGESTION_HIGH_FROM:
        return CongestionLevel.HIGH
    if waiting_count >= CONGESTION_MID_FROM:
        return CongestionLevel.MID
    return CongestionLevel.LOW


# 운항 여건 점수(풍속·시정 기반 자체 계산). 임시 공식이며 실제 운항 확률이 아니다.
# 풍속: WIND_OK 이하면 감점 없음, WIND_LIMIT 이상이면 최대 감점. 시정은 반대 방향.
WIND_OK_MS = 10.0
WIND_LIMIT_MS = 25.0
VISIBILITY_OK_KM = 5.0
VISIBILITY_LIMIT_KM = 0.8
MAX_PENALTY_PER_FACTOR = 50.0
SCORE_HIGH_FROM = 80
SCORE_MID_FROM = 50
OPERATION_SCORE_MINUTES_AHEAD = 60

OPERATION_MESSAGES: dict[OperationLevel, str] = {
    OperationLevel.HIGH: "운항 여건 양호",
    OperationLevel.MID: "운항 여건 보통",
    OperationLevel.LOW: "운항 여건 주의",
}
OPERATION_MESSAGE_NO_DATA = "데이터 부족"


def _penalty(value: float, ok: float, limit: float) -> float:
    """ok에서 limit 쪽으로 갈수록 0 → MAX_PENALTY_PER_FACTOR로 선형 증가."""
    ratio = (value - ok) / (limit - ok)
    return MAX_PENALTY_PER_FACTOR * min(max(ratio, 0.0), 1.0)


def operation_score(wind_speed: float | None, visibility: float | None) -> int | None:
    if wind_speed is None or visibility is None:
        return None
    score = (
        100
        - _penalty(wind_speed, WIND_OK_MS, WIND_LIMIT_MS)
        - _penalty(visibility, VISIBILITY_OK_KM, VISIBILITY_LIMIT_KM)
    )
    return round(score)


def operation_level(score: int | None) -> OperationLevel | None:
    if score is None:
        return None
    if score >= SCORE_HIGH_FROM:
        return OperationLevel.HIGH
    if score >= SCORE_MID_FROM:
        return OperationLevel.MID
    return OperationLevel.LOW
