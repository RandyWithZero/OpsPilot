from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class FoundationAPIError(Exception):
    def __init__(self, status: int, error: str) -> None:
        super().__init__(error)
        self.status = status
        self.error = error


class NoRuntimeTask(FoundationAPIError):
    pass


@dataclass(frozen=True)
class FoundationAPIClient:
    base_url: str
    access_token: str
    timeout_seconds: float = 10.0

    def list_agents(self) -> list[dict[str, Any]]:
        return self._request("GET", "/v1/agents")

    def list_skills(self) -> list[dict[str, Any]]:
        return self._request("GET", "/v1/skills")

    def list_model_providers(self) -> list[dict[str, Any]]:
        return self._request("GET", "/v1/model-providers")

    def claim_runtime_task(self, *, agent_id: str = "", worker_id: str = "", lease_seconds: int = 60) -> dict[str, Any]:
        body: dict[str, Any] = {"lease_seconds": lease_seconds}
        if agent_id:
            body["agent_id"] = agent_id
        if worker_id:
            body["worker_id"] = worker_id
        try:
            return self._request("POST", "/v1/runtime/tasks/claim", body)
        except FoundationAPIError as exc:
            if exc.status == 404:
                raise NoRuntimeTask(exc.status, exc.error) from exc
            raise

    def callback_runtime_task(self, task_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"/v1/runtime/tasks/{task_id}/callback", body)

    def update_workflow_step(self, run_id: str, step_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._request("PATCH", f"/v1/workflow-runs/{run_id}/steps/{step_id}", body)

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None, query: dict[str, str] | None = None) -> Any:
        url = f"{self.base_url.rstrip('/')}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        payload = None if body is None else json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
        request = Request(url, data=payload, method=method)
        request.add_header("Authorization", f"Bearer {self.access_token}")
        request.add_header("Accept", "application/json")
        if payload is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                data = response.read()
                return json.loads(data.decode("utf-8")) if data else None
        except HTTPError as exc:
            error = "http_error"
            try:
                payload_data = json.loads(exc.read().decode("utf-8"))
                error = str(payload_data.get("error") or error)
            except (ValueError, json.JSONDecodeError):
                pass
            raise FoundationAPIError(exc.code, error) from exc
