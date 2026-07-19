"""MatchDay Copilot — FastAPI application.

Security posture:
- All inputs validated by Pydantic schemas (length caps, ID patterns,
  unknown fields rejected).
- Simple in-memory per-IP rate limiting on the GenAI endpoint.
- Security headers on every response; no secrets in code.
"""

import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from .config import get_settings
from .models import (
    AskRequest,
    AskResponse,
    CrowdResponse,
    NavigateRequest,
    NavigateResponse,
)
from .services import assistant, crowd, navigation

app = FastAPI(
    title="MatchDay Copilot",
    description="GenAI matchday assistant for fans at FIFA World Cup 2026 venues.",
    version="1.0.0",
)

STATIC_DIR = Path(__file__).resolve().parent / "static"

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

_request_log: dict[str, deque] = defaultdict(deque)


def _rate_limited(client_ip: str, limit_per_minute: int) -> bool:
    now = time.monotonic()
    window = _request_log[client_ip]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= limit_per_minute:
        return True
    window.append(now)
    return False


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "script-src 'self' 'unsafe-inline'; img-src 'self' data:"
    )
    return response


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict:
    settings = get_settings()
    return {"status": "ok", "genai_enabled": settings.llm_enabled}


@app.get("/api/venues")
async def venues() -> dict:
    vs = navigation.load_venues()
    return {
        "venues": [
            {
                "id": v["id"],
                "name": v["name"],
                "city": v["city"],
                "capacity": v["capacity"],
                "nodes": [
                    {"id": nid, "label": n["label"], "type": n["type"], "step_free": n["step_free"]}
                    for nid, n in v["nodes"].items()
                ],
            }
            for v in vs.values()
        ]
    }


@app.get("/api/matches")
async def matches() -> dict:
    return {"matches": assistant.load_matches()}


@app.get("/api/crowd/{venue_id}", response_model=CrowdResponse)
async def crowd_snapshot(venue_id: str) -> CrowdResponse:
    snap = crowd.snapshot(venue_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="Unknown venue")
    return CrowdResponse(**snap)


@app.post("/api/navigate", response_model=NavigateResponse)
async def navigate(payload: NavigateRequest) -> NavigateResponse:
    route = navigation.find_route(
        payload.venue_id, payload.start, payload.destination, payload.step_free_only
    )
    if route is None:
        raise HTTPException(status_code=404, detail="Unknown venue or location")
    if not route["found"]:
        route["note"] = (
            "No step-free path connects those points; ask a steward about lift access."
            if payload.step_free_only
            else "No path found between those points."
        )
    return NavigateResponse(**route)


@app.post("/api/ask", response_model=AskResponse)
async def ask(payload: AskRequest, request: Request) -> AskResponse:
    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    if _rate_limited(client_ip, settings.rate_limit_per_minute):
        raise HTTPException(status_code=429, detail="Too many requests; please slow down.")
    if navigation.get_venue(payload.venue_id) is None:
        raise HTTPException(status_code=404, detail="Unknown venue")
    result = await assistant.ask(
        payload.question,
        payload.venue_id,
        payload.language,
        payload.accessibility_needs,
        settings,
    )
    return AskResponse(language=payload.language, **result)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    # Never leak stack traces or internals to clients.
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
