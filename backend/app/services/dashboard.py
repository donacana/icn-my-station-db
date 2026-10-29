from app.core import rules
from app.core.timeutil import now_kst
from app.schemas import (
    DashboardSummary,
    Direction,
    SummaryCongestion,
    SummaryFlights,
    SummaryStats,
    Terminal,
)
from app.services import alerts, congestion, facilities, flights, stats, weather


def get_summary(flight_no: str | None = None) -> DashboardSummary:
    my_flight_no = flights.resolve_my_flight_no(flight_no)
    limit = rules.SUMMARY_FLIGHT_LIMIT
    return DashboardSummary(
        generated_at=now_kst(),
        my_flight_no=my_flight_no,
        flights=SummaryFlights(
            departures=flights.list_flights(Direction.DEPARTURE, my_flight_no)[:limit],
            arrivals=flights.list_flights(Direction.ARRIVAL, my_flight_no)[:limit],
        ),
        congestion=SummaryCongestion(
            T1=congestion.get_congestion(Terminal.T1),
            T2=congestion.get_congestion(Terminal.T2),
        ),
        stats=SummaryStats(
            departure=stats.get_flight_stats(Direction.DEPARTURE),
            arrival=stats.get_flight_stats(Direction.ARRIVAL),
        ),
        alerts=alerts.list_alerts(my_flight_no),
        weather=weather.get_weather(),
        facilities=facilities.list_facilities(),
    )
