import os
from datetime import UTC, datetime
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
CROWDSEC_MACHINE_LOGIN = os.getenv("CROWDSEC_MACHINE_LOGIN", "")
CROWDSEC_MACHINE_PASSWORD = os.getenv("CROWDSEC_MACHINE_PASSWORD", "")
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "10"))


def _headers(token: str | None = None) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif CROWDSEC_API_KEY:
        headers["X-Api-Key"] = CROWDSEC_API_KEY
    return headers


def _has_machine_auth() -> bool:
    return bool(CROWDSEC_MACHINE_LOGIN and CROWDSEC_MACHINE_PASSWORD)


def _has_any_auth() -> bool:
    return _has_machine_auth() or bool(CROWDSEC_API_KEY)


def _is_write_method(method: str) -> bool:
    return method.upper() in {"POST", "PUT", "PATCH", "DELETE"}


async def _get_machine_token(client: httpx.AsyncClient) -> str:
    auth_url = f"{CROWDSEC_API_URL}/v1/watchers/login"
    payloads = [
        {"machine_id": CROWDSEC_MACHINE_LOGIN, "password": CROWDSEC_MACHINE_PASSWORD},
        {"login": CROWDSEC_MACHINE_LOGIN, "password": CROWDSEC_MACHINE_PASSWORD},
    ]
    last_error = ""

    for payload in payloads:
        response = await client.post(auth_url, json=payload, headers={"Accept": "application/json"})
        if response.status_code >= 400:
            last_error = response.text
            continue

        try:
            data = response.json()
        except ValueError:
            data = {}

        token = data.get("token") or data.get("jwt") or data.get("access_token")
        if isinstance(token, str) and token:
            return token

        raw = response.text.strip()
        if raw:
            return raw

    raise HTTPException(
        status_code=502,
        detail=(
            "Failed to authenticate CROWDSEC_MACHINE_LOGIN/CROWDSEC_MACHINE_PASSWORD against CrowdSec LAPI. "
            f"Last response: {last_error}"
        ),
    )


async def _lapi_request(method: str, path: str, **kwargs: Any) -> Any:
    if not _has_any_auth():
        raise HTTPException(
            status_code=500,
            detail="Configure CROWDSEC_API_KEY or CROWDSEC_MACHINE_LOGIN/CROWDSEC_MACHINE_PASSWORD",
        )

    url = f"{CROWDSEC_API_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            is_write = _is_write_method(method)
            token: str | None = None
            headers: dict[str, str]

            if is_write:
                if _has_machine_auth():
                    token = await _get_machine_token(client)
                    headers = _headers(token)
                elif CROWDSEC_API_KEY:
                    headers = _headers(None)
                else:
                    raise HTTPException(
                        status_code=500,
                        detail=(
                            "Write operations require CROWDSEC_MACHINE_LOGIN and CROWDSEC_MACHINE_PASSWORD "
                            "(or may fail with read-only bouncer key)."
                        ),
                    )
            else:
                if CROWDSEC_API_KEY:
                    headers = _headers(None)
                elif _has_machine_auth():
                    token = await _get_machine_token(client)
                    headers = _headers(token)
                else:
                    raise HTTPException(
                        status_code=500,
                        detail="Read operations require CROWDSEC_API_KEY or machine credentials.",
                    )

            response = await client.request(method=method, url=url, headers=headers, **kwargs)
            if response.status_code >= 400:
                if is_write and response.status_code == 405 and not _has_machine_auth() and CROWDSEC_API_KEY:
                    raise HTTPException(
                        status_code=403,
                        detail=(
                            "Write access denied. Bouncer API keys are read-only in CrowdSec LAPI. "
                            "Configure CROWDSEC_MACHINE_LOGIN and CROWDSEC_MACHINE_PASSWORD to create/delete decisions."
                        ),
                    )
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
    scope = str(payload.get("scope", "ip")).lower()
    value = payload.get("value")
    decision_type = payload.get("type", "ban")
    duration = payload.get("duration", "4h")
    origin = payload.get("origin", "cscli")
    scenario = payload.get("scenario", f"manual '{decision_type}' from 'crowdsec-webui'")

    if not value:
        raise HTTPException(status_code=400, detail="Field 'value' is required")
    if scope not in {"ip", "range", "username", "country", "as", "value"}:
        raise HTTPException(status_code=400, detail=f"Unsupported scope '{scope}'")

    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    source_ip = value if scope == "ip" else ""
    source_range = value if scope == "range" else ""
    alert_payload = [
        {
            "capacity": 0,
            "events_count": 1,
            "leakspeed": "0",
            "message": scenario,
            "scenario": scenario,
            "scenario_hash": "",
            "scenario_version": "",
            "simulated": False,
            "start_at": now,
            "stop_at": now,
            "created_at": now,
            "kind": "manual",
            "remediation": True,
            "source": {
                "scope": scope,
                "value": value,
                "ip": source_ip,
                "range": source_range,
                "as_number": "",
                "as_name": "",
                "cn": "",
            },
            "decisions": [
                {
                    "duration": duration,
                    "scope": scope,
                    "value": value,
                    "type": decision_type,
                    "scenario": scenario,
                    "origin": origin,
                }
            ],
            "events": [],
        }
    ]

    return await _lapi_request("POST", "/v1/alerts", json=alert_payload)


@app.delete("/api/decisions/{decision_id}")
async def delete_decision(decision_id: int) -> Any:
    return await _lapi_request("DELETE", f"/v1/decisions/{decision_id}")
