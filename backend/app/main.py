from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import ws
from app.core.config import settings
from app.routers import alerts, congestion, dashboard, facilities, flights, stats, weather
from app.services.flights import FlightNotFoundError

API_PREFIX = "/api/v1"

app = FastAPI(title="ICN My Station API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(FlightNotFoundError)
def flight_not_found_handler(_: Request, exc: FlightNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


for module in (dashboard, flights, congestion, stats, alerts, weather, facilities):
    app.include_router(module.router, prefix=API_PREFIX)
app.include_router(ws.router)
