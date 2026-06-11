#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


WEB_URL = os.environ.get("OPSPILOT_SMOKE_WEB_URL", "http://127.0.0.1:15173").rstrip("/")
TIMEOUT_SECONDS = float(os.environ.get("OPSPILOT_SMOKE_TIMEOUT_SECONDS", "90"))
DEV_LOGIN_PASSWORD = os.environ.get("OPSPILOT_AUTH_DEV_PASSWORD", "")


def main() -> None:
    wait_for_gateway()
    index = request_text("GET", "/")
    if "OpsPilot" not in index or "app.js" not in index:
        raise RuntimeError("web gateway did not serve the console shell")

    health = request_json("GET", "/healthz")
    if health.get("status") != "ok":
        raise RuntimeError(f"unexpected health status through web gateway: {health}")

    readiness = request_json("GET", "/readyz")
    if readiness.get("dependencies", {}).get("store", {}).get("status") != "ok":
        raise RuntimeError(f"foundation store is not ready through web gateway: {readiness}")

    expect_http_error(
        "POST",
        "/v1/auth/login",
        {"actor_id": "usr_web_smoke", "role": "Admin", "email": "web-smoke@local.opspilot", "name": "Web Smoke", "password": ""},
        401,
        "empty password login",
    )

    if not DEV_LOGIN_PASSWORD:
        raise RuntimeError("OPSPILOT_AUTH_DEV_PASSWORD is required for web gateway smoke login")

    session = request_json(
        "POST",
        "/v1/auth/login",
        {"actor_id": "usr_web_smoke", "role": "Admin", "email": "web-smoke@local.opspilot", "name": "Web Smoke", "password": DEV_LOGIN_PASSWORD},
    )
    token = session.get("access_token")
    if not token:
        raise RuntimeError("login through web gateway did not return an access token")

    projects = request_json("GET", "/v1/projects", headers={"Authorization": f"Bearer {token}"})
    if not isinstance(projects, list):
        raise RuntimeError("projects API through web gateway did not return a list")

    print(f"web gateway smoke passed: {WEB_URL}")


def wait_for_gateway() -> None:
    deadline = time.time() + TIMEOUT_SECONDS
    last_error = ""
    while time.time() < deadline:
        try:
            request_json("GET", "/readyz")
            return
        except Exception as exc:
            last_error = str(exc)
        time.sleep(2)
    raise RuntimeError(f"web gateway was not ready within {TIMEOUT_SECONDS:.0f}s: {last_error}")


def request_json(method: str, path: str, body: dict[str, Any] | None = None, *, headers: dict[str, str] | None = None) -> Any:
    payload = request(method, path, body, headers=headers)
    return json.loads(payload.decode("utf-8")) if payload else {}


def request_text(method: str, path: str, body: dict[str, Any] | None = None, *, headers: dict[str, str] | None = None) -> str:
    return request(method, path, body, headers=headers).decode("utf-8")


def request(method: str, path: str, body: dict[str, Any] | None = None, *, headers: dict[str, str] | None = None) -> bytes:
    data = None if body is None else json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    req = Request(f"{WEB_URL}{path}", data=data, method=method)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urlopen(req, timeout=10) as response:
            return response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed with {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"{method} {path} failed: {exc}") from exc


def expect_http_error(method: str, path: str, body: dict[str, Any], status: int, label: str) -> None:
    data = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    req = Request(f"{WEB_URL}{path}", data=data, method=method)
    req.add_header("Accept", "application/json")
    req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=10) as response:
            raise RuntimeError(f"{label} unexpectedly succeeded with {response.status}")
    except HTTPError as exc:
        if exc.code != status:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{label} expected {status}, got {exc.code}: {detail}") from exc


if __name__ == "__main__":
    main()
