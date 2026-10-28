"""WebSocket으로 보낼 메시지를 만든다. data는 해당 REST 응답과 같은 모양이다."""

from pydantic import BaseModel

from app.core.timeutil import now_kst
from app.schemas import Direction, LiveMessage, LiveTopic, Terminal
from app.services import alerts, congestion, flights, stats, weather


def _dump(data: BaseModel | list[BaseModel]):
    if isinstance(data, list):
        return [item.model_dump(mode="json", by_alias=True) for item in data]
    return data.model_dump(mode="json", by_alias=True)


def build_snapshot() -> list[LiveMessage]:
    """토픽별 현재 상태. congestion은 터미널별, flights·stats는 방향별로 따로 보낸다."""
    sent_at = now_kst()
    payloads: list[tuple[LiveTopic, BaseModel | list[BaseModel]]] = [
        *((LiveTopic.CONGESTION, congestion.get_congestion(t)) for t in Terminal),
        *((LiveTopic.FLIGHTS, flights.list_flights(d)) for d in Direction),
        *((LiveTopic.STATS, stats.get_flight_stats(d)) for d in Direction),
        (LiveTopic.ALERTS, alerts.list_alerts()),
        (LiveTopic.WEATHER, weather.get_weather()),
    ]
    return [LiveMessage(topic=topic, data=_dump(data), sent_at=sent_at) for topic, data in payloads]
