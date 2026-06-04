from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import urlparse

from .domain import DomainError
from .store import MemoryStore


class FoundationHandler(BaseHTTPRequestHandler):
    store = MemoryStore()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        routes: dict[str, Callable[[], Any]] = {
            "/healthz": self.store.health,
            "/v1/users": self.store.list_users,
            "/v1/projects": self.store.list_projects,
            "/v1/assets": self.store.list_assets,
            "/v1/environments": self.store.list_environments,
            "/v1/audit-events": self.store.list_audit_events,
        }
        path = urlparse(self.path).path
        if path not in routes:
            self._json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            return
        self._call(routes[path])

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            body = self._body()
        except BadJSON:
            self._json({"error": "invalid_json"}, HTTPStatus.BAD_REQUEST)
            return
        actor_id = self.headers.get("X-Actor-ID", "")

        if path == "/v1/users":
            self._call(lambda: self.store.create_user(actor_id, body), HTTPStatus.CREATED)
            return
        if path == "/v1/projects":
            self._call(lambda: self.store.create_project(actor_id, body), HTTPStatus.CREATED)
            return
        if path == "/v1/assets":
            self._call(lambda: self.store.create_asset(actor_id, body), HTTPStatus.CREATED)
            return
        if path == "/v1/environments":
            self._call(lambda: self.store.create_environment(actor_id, body), HTTPStatus.CREATED)
            return

        parts = [part for part in path.split("/") if part]
        if len(parts) == 5 and parts[:2] == ["v1", "projects"] and parts[3] == "assets":
            self._call(lambda: self.store.link_project_asset(actor_id, parts[2], parts[4]))
            return
        if len(parts) == 5 and parts[:2] == ["v1", "projects"] and parts[3] == "environments":
            self._call(lambda: self.store.link_project_environment(actor_id, parts[2], parts[4]))
            return

        self._json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

    def do_PATCH(self) -> None:
        path = urlparse(self.path).path
        try:
            body = self._body()
        except BadJSON:
            self._json({"error": "invalid_json"}, HTTPStatus.BAD_REQUEST)
            return
        actor_id = self.headers.get("X-Actor-ID", "")
        parts = [part for part in path.split("/") if part]

        if len(parts) == 3 and parts[:2] == ["v1", "users"]:
            self._call(lambda: self.store.update_user(actor_id, parts[2], body))
            return
        if len(parts) == 3 and parts[:2] == ["v1", "projects"]:
            self._call(lambda: self.store.update_project(actor_id, parts[2], body))
            return
        if len(parts) == 3 and parts[:2] == ["v1", "assets"]:
            self._call(lambda: self.store.update_asset(actor_id, parts[2], body))
            return
        if len(parts) == 3 and parts[:2] == ["v1", "environments"]:
            self._call(lambda: self.store.update_environment(actor_id, parts[2], body))
            return

        self._json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        actor_id = self.headers.get("X-Actor-ID", "")
        parts = [part for part in path.split("/") if part]

        if len(parts) == 3 and parts[:2] == ["v1", "users"]:
            self._call(lambda: self.store.delete_user(actor_id, parts[2]))
            return
        if len(parts) == 3 and parts[:2] == ["v1", "projects"]:
            self._call(lambda: self.store.delete_project(actor_id, parts[2]))
            return
        if len(parts) == 3 and parts[:2] == ["v1", "assets"]:
            self._call(lambda: self.store.delete_asset(actor_id, parts[2]))
            return
        if len(parts) == 3 and parts[:2] == ["v1", "environments"]:
            self._call(lambda: self.store.delete_environment(actor_id, parts[2]))
            return
        if len(parts) == 5 and parts[:2] == ["v1", "projects"] and parts[3] == "assets":
            self._call(lambda: self.store.unlink_project_asset(actor_id, parts[2], parts[4]))
            return
        if len(parts) == 5 and parts[:2] == ["v1", "projects"] and parts[3] == "environments":
            self._call(lambda: self.store.unlink_project_environment(actor_id, parts[2], parts[4]))
            return

        self._json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _body(self) -> dict[str, Any]:
        size = int(self.headers.get("Content-Length", "0"))
        if size == 0:
            return {}
        try:
            body = json.loads(self.rfile.read(size).decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise BadJSON(str(exc)) from exc
        if not isinstance(body, dict):
            raise BadJSON("request body must be an object")
        return body

    def _call(self, fn: Callable[[], Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        try:
            self._json(fn(), status)
        except BadJSON:
            self._json({"error": "invalid_json"}, HTTPStatus.BAD_REQUEST)
        except DomainError as exc:
            self._json({"error": exc.code}, exc.status)

    def _json(self, payload: Any, status: int | HTTPStatus) -> None:
        data = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self.send_response(int(status))
        self._cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,X-Actor-ID")


class BadJSON(Exception):
    pass


def run() -> None:
    addr = os.environ.get("HTTP_ADDR", "0.0.0.0:8080")
    host, port = addr.rsplit(":", 1)
    server = ThreadingHTTPServer((host, int(port)), FoundationHandler)
    print(f"foundation-service listening on {addr}")
    server.serve_forever()


if __name__ == "__main__":
    run()
