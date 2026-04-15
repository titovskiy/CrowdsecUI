import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request


app = FastAPI(title="CrowdSec WebUI")

templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

CROWDSEC_API_URL = os.getenv("CROWDSEC_API_URL", "http://crowdsec:8080").rstrip("/")
CROWDSEC_API_KEY = os.getenv("CROWDSEC_API_KEY", "")
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "10"))


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if CROWDSEC_API_KEY:
        headers["X-Api-Key"] = CROWDSEC_API_KEY
    return headers


async def _lapi_request(method: str, path: str, **kwargs: Any) -> Any:
    if not CROWDSEC_API_KEY:
        raise HTTPException(status_code=500, detail="CROWDSEC_API_KEY is not configured")

    url = f"{CROWDSEC_API_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.request(method=method, url=url, headers=_headers(), **kwargs)
            if response.status_code >= 400:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            if response.text:
                return response.json()
            return {"ok": True}
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Cannot connect to CrowdSec LAPI: {exc}") from exc


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/health")
async def health() -> Any:
    return await _lapi_request("GET", "/health")


@app.get("/api/decisions")
async def list_decisions(
    scope: str | None = Query(default=None),
    value: str | None = Query(default=None),
    decision_type: str | None = Query(default=None, alias="type"),
    origin: str | None = Query(default=None),
    scenario: str | None = Query(default=None),
    contains: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> Any:
    params: dict[str, Any] = {"limit": limit}
    if scope:
        params["scope"] = scope
    if value:
        params["value"] = value
    if decision_type:
        params["type"] = decision_type
    if origin:
        params["origin"] = origin
    if scenario:
        params["scenario"] = scenario
    if contains is not None:
        params["contains"] = str(contains).lower()

    return await _lapi_request("GET", "/v1/decisions", params=params)


@app.post("/api/decisions")
async def create_decision(payload: dict[str, Any]) -> Any:
    normalized = {
        "scope": payload.get("scope", "ip"),
        "value": payload.get("value"),
        "type": payload.get("type", "ban"),
        "duration": payload.get("duration", "4h"),
        "origin": payload.get("origin", "crowdsec-webui"),
        "scenario": payload.get("scenario", "manual"),
    }

    if not normalized["value"]:
        raise HTTPException(status_code=400, detail="Field 'value' is required")

    return await _lapi_request("POST", "/v1/decisions", json=normalized)


@app.delete("/api/decisions/{decision_id}")
async def delete_decision(decision_id: int) -> Any:
    return await _lapi_request("DELETE", f"/v1/decisions/{decision_id}")
