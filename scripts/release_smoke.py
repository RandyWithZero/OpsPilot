#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = os.environ.get("OPSPILOT_SMOKE_FOUNDATION_URL", os.environ.get("OPSPILOT_FOUNDATION_URL", "http://127.0.0.1:8080")).rstrip("/")
TIMEOUT_SECONDS = float(os.environ.get("OPSPILOT_SMOKE_TIMEOUT_SECONDS", "90"))
DEV_LOGIN_PASSWORD = os.environ.get("OPSPILOT_AUTH_DEV_PASSWORD", "")


def main() -> None:
    wait_for_ready()
    suffix = uuid.uuid4().hex[:8]
    if not DEV_LOGIN_PASSWORD:
        raise RuntimeError("OPSPILOT_AUTH_DEV_PASSWORD is required for release smoke login")
    session = request("POST", "/v1/auth/login", {"actor_id": "usr_smoke_admin", "role": "Admin", "email": "smoke@local.opspilot", "name": "Smoke Admin", "password": DEV_LOGIN_PASSWORD})
    admin_token = session["access_token"]
    headers = auth(admin_token)

    project = request("POST", "/v1/projects", {"key": f"SMOKE{suffix}", "name": f"Release Smoke {suffix}", "owner_id": "usr_smoke_admin"}, headers=headers)
    uploaded = request(
        "POST",
        "/v1/files/upload",
        {
            "filename": "smoke.txt",
            "content_type": "text/plain",
            "owner_id": "usr_smoke_admin",
            "resource_type": "project",
            "resource_id": project["id"],
            "module": "release-smoke",
            "content_base64": base64.b64encode(b"release smoke artifact").decode("ascii"),
        },
        headers=headers,
    )
    downloaded = request("GET", f"/v1/files/{uploaded['id']}/download?owner_id=usr_smoke_admin", headers=headers)
    assert_equal(base64.b64decode(downloaded["content_base64"]), b"release smoke artifact", "file upload/download")

    suite = request("POST", "/v1/test-suites", {"project_id": project["id"], "name": "Release Smoke"}, headers=headers)
    test_run = request("POST", "/v1/test-runs", {"project_id": project["id"], "suite_id": suite["id"]}, headers=headers)
    junit = b'<testsuite tests="1" failures="0" errors="0"><testcase classname="smoke" name="release"/></testsuite>'
    ingest = request(
        "POST",
        f"/v1/test-runs/{test_run['id']}/artifacts",
        {"title": "Release Smoke", "artifacts": [{"filename": "junit.xml", "content_type": "application/xml", "artifact_type": "junit", "content_base64": base64.b64encode(junit).decode("ascii")}]},
        headers=headers,
    )
    assert_equal(ingest["quality_gate"]["status"], "passed", "artifact quality gate")

    identity = request("POST", "/v1/service-identities", {"name": f"release-smoke-worker-{suffix}", "role": "Operator", "project_ids": [project["id"]]}, headers=headers)
    credential = request("POST", "/v1/credentials", {"provider": "model_provider", "name": f"Smoke Model Key {suffix}", "secret": "smoke-model-key"}, headers=headers)
    provider = request("POST", "/v1/model-providers", {"provider": "local", "name": f"Smoke Provider {suffix}", "credential_ref_id": credential["id"]}, headers=headers)
    skill = request("POST", "/v1/skills", {"name": f"Release Smoke Skill {suffix}", "version": "1.0.0", "runtime": "mock"}, headers=headers)
    agent = request("POST", "/v1/agents", {"name": f"Release Smoke Agent {suffix}", "kind": "automation", "skill_ids": [skill["id"]], "model_provider_id": provider["id"]}, headers=headers)
    workflow = request("POST", "/v1/workflows", {"name": f"Release Smoke Workflow {suffix}", "project_id": project["id"]}, headers=headers)
    request(
        "POST",
        f"/v1/workflows/{workflow['id']}/versions",
        {
            "version": "1",
            "nodes": [
                {"id": "start", "type": "trigger"},
                {"id": "agent", "type": "agent_task", "agent_id": agent["id"], "skill_id": skill["id"], "model_provider_id": provider["id"], "config": {"api_key": "must-not-leak"}},
                {"id": "done", "type": "result"},
            ],
            "edges": [{"from_node_id": "start", "to_node_id": "agent"}, {"from_node_id": "agent", "to_node_id": "done"}],
        },
        headers=headers,
    )
    run = request("POST", f"/v1/workflows/{workflow['id']}/runs", {"start": True}, headers=headers)
    worker_token = request("POST", f"/v1/service-identities/{identity['id']}/token", {"service_token": identity["service_token"]})["access_token"]
    run_worker_once(worker_token)
    completed = request("GET", f"/v1/workflows/{workflow['id']}/runs", headers=headers)[0]
    assert_equal(completed["status"], "completed", "workflow worker completion")

    readiness = request("GET", "/readyz")
    if readiness["status"] not in {"ok", "degraded"}:
        raise RuntimeError(f"unexpected readiness status: {readiness['status']}")
    serialized = json.dumps({"readiness": readiness, "run": completed}, sort_keys=True)
    for forbidden in ("smoke-model-key", "must-not-leak", "attempt_token"):
        if forbidden in serialized:
            raise RuntimeError(f"smoke response leaked sensitive value: {forbidden}")
    print("release smoke passed")


def wait_for_ready() -> None:
    deadline = time.time() + TIMEOUT_SECONDS
    last_error = ""
    while time.time() < deadline:
        try:
            readiness = request("GET", "/readyz")
            if readiness.get("dependencies", {}).get("store", {}).get("status") == "ok" and readiness.get("dependencies", {}).get("storage", {}).get("status") == "ok":
                return
            last_error = json.dumps(readiness, sort_keys=True)
        except Exception as exc:
            last_error = str(exc)
        time.sleep(2)
    raise RuntimeError(f"foundation service was not ready within {TIMEOUT_SECONDS:.0f}s: {last_error}")


def request(method: str, path: str, body: dict[str, Any] | None = None, *, headers: dict[str, str] | None = None) -> Any:
    data = None if body is None else json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    req = Request(f"{BASE_URL}{path}", data=data, method=method)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urlopen(req, timeout=10) as response:
            payload = response.read()
            return json.loads(payload.decode("utf-8")) if payload else {}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed with {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"{method} {path} failed: {exc}") from exc


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def run_worker_once(access_token: str) -> None:
    workspace = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(workspace / "services" / "agent-worker"))
    from opspilot_agent_worker.api import FoundationAPIClient
    from opspilot_agent_worker.worker import AgentWorker, WorkerConfig

    api = FoundationAPIClient(BASE_URL, access_token)
    worker = AgentWorker(api, WorkerConfig(worker_id="release-smoke-worker", lease_seconds=30, once=True))
    if not worker.poll_once():
        raise RuntimeError("worker found no runtime task to process")


def assert_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise RuntimeError(f"{label} expected {expected!r}, got {actual!r}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"release smoke failed: {exc}", file=sys.stderr)
        raise
