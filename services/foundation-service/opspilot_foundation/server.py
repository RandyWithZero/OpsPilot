from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import urlparse

from .auth import actor_from_headers, permission_for_request, require_permission
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
            "/v1/files": self.store.list_file_objects,
            "/v1/credentials": self.store.list_credentials,
            "/v1/gitlab/profiles": self.store.list_gitlab_profiles,
            "/v1/vcs/operations": self.store.list_vcs_operations,
            "/v1/vcs/webhook-events": self.store.list_vcs_webhook_events,
            "/v1/agents": self.store.list_agents,
            "/v1/skills": self.store.list_skills,
            "/v1/model-providers": self.store.list_model_providers,
            "/v1/workflows": self.store.list_workflows,
            "/v1/workflow-runs": self.store.list_workflow_runs,
            "/v1/test-cases": self.store.list_test_cases,
            "/v1/test-suites": self.store.list_test_suites,
            "/v1/test-runs": self.store.list_test_runs,
            "/v1/reports": self.store.list_reports,
            "/v1/quality-gates": self.store.list_quality_gates,
            "/v1/audit-events": self.store.list_audit_events,
        }
        path = urlparse(self.path).path
        actor = actor_from_headers(self.headers)
        if not self._authorize(actor, "GET", path):
            return
        parts = [part for part in path.split("/") if part]
        if len(parts) == 5 and parts[:3] == ["v1", "gitlab", "profiles"] and parts[4] == "repositories":
            self._call(lambda: self.store.list_gitlab_repositories(parts[3]))
            return
        if len(parts) == 4 and parts[:2] == ["v1", "workflows"] and parts[3] == "versions":
            self._call(lambda: self.store.list_workflow_versions(parts[2]))
            return
        if len(parts) == 4 and parts[:2] == ["v1", "workflows"] and parts[3] == "runs":
            self._call(lambda: self.store.list_workflow_runs(parts[2]))
            return
        if path in routes:
            self._call(routes[path])
            return
        self._json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            body = self._body()
        except BadJSON:
            self._json({"error": "invalid_json"}, HTTPStatus.BAD_REQUEST)
            return
        actor = actor_from_headers(self.headers)
        if not self._authorize(actor, "POST", path, body):
            return
        actor_id = actor.actor_id

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
        if path == "/v1/files":
            self._call(lambda: self.store.create_file_object(actor_id, body), HTTPStatus.CREATED)
            return
        if path == "/v1/credentials":
            self._call(lambda: self.store.create_credential(actor_id, body), HTTPStatus.CREATED)
            return
        if path == "/v1/gitlab/profiles":
            self._call(lambda: self.store.create_gitlab_profile(actor_id, body), HTTPStatus.CREATED)
            return
        if path == "/v1/vcs/operations":
            self._call(lambda: self.store.create_vcs_operation(actor_id, body), HTTPStatus.CREATED)
            return
        if path == "/v1/vcs/webhook-events":
            self._call(lambda: self.store.ingest_vcs_webhook_event(actor_id, body), HTTPStatus.CREATED)
            return
        if path == "/v1/agents":
            self._call(lambda: self.store.create_agent(actor_id, body), HTTPStatus.CREATED)
            return
        if path == "/v1/skills":
            self._call(lambda: self.store.create_skill(actor_id, body), HTTPStatus.CREATED)
            return
        if path == "/v1/model-providers":
            self._call(lambda: self.store.create_model_provider(actor_id, body), HTTPStatus.CREATED)
            return
        if path == "/v1/workflows":
            self._call(lambda: self.store.create_workflow(actor_id, body), HTTPStatus.CREATED)
            return
        if path == "/v1/test-cases":
            self._call(lambda: self.store.create_test_case(actor_id, body), HTTPStatus.CREATED)
            return
        if path == "/v1/test-suites":
            self._call(lambda: self.store.create_test_suite(actor_id, body), HTTPStatus.CREATED)
            return
        if path == "/v1/test-runs":
            self._call(lambda: self.store.create_test_run(actor_id, body), HTTPStatus.CREATED)
            return
        if path == "/v1/reports":
            self._call(lambda: self.store.create_report(actor_id, body), HTTPStatus.CREATED)
            return
        if path == "/v1/quality-gates":
            self._call(lambda: self.store.create_quality_gate(actor_id, body), HTTPStatus.CREATED)
            return

        parts = [part for part in path.split("/") if part]
        if len(parts) == 4 and parts[:2] == ["v1", "files"] and parts[3] == "upload-grants":
            self._call(lambda: self.store.create_upload_grant(actor_id, parts[2]), HTTPStatus.CREATED)
            return
        if len(parts) == 4 and parts[:2] == ["v1", "files"] and parts[3] == "upload-sessions":
            self._call(lambda: self.store.create_upload_session(actor_id, parts[2]), HTTPStatus.CREATED)
            return
        if len(parts) == 5 and parts[:3] == ["v1", "files", "upload-sessions"] and parts[4] == "complete":
            self._call(lambda: self.store.complete_upload_session(actor_id, parts[3], body))
            return
        if len(parts) == 4 and parts[:2] == ["v1", "files"] and parts[3] == "download-grants":
            self._call(lambda: self.store.create_download_grant(actor_id, parts[2]), HTTPStatus.CREATED)
            return
        if len(parts) == 5 and parts[:2] == ["v1", "projects"] and parts[3] == "assets":
            self._call(lambda: self.store.link_project_asset(actor_id, parts[2], parts[4]))
            return
        if len(parts) == 5 and parts[:2] == ["v1", "projects"] and parts[3] == "environments":
            self._call(lambda: self.store.link_project_environment(actor_id, parts[2], parts[4]))
            return
        if len(parts) == 4 and parts[:2] == ["v1", "projects"] and parts[3] == "repositories":
            self._call(lambda: self.store.link_project_repository(actor_id, parts[2], body))
            return
        if len(parts) == 4 and parts[:2] == ["v1", "workflows"] and parts[3] == "versions":
            self._call(lambda: self.store.create_workflow_version(actor_id, parts[2], body), HTTPStatus.CREATED)
            return
        if len(parts) == 4 and parts[:2] == ["v1", "workflows"] and parts[3] == "runs":
            self._call(lambda: self.store.create_workflow_run(actor_id, parts[2], body), HTTPStatus.CREATED)
            return
        if len(parts) == 4 and parts[:2] == ["v1", "workflow-runs"] and parts[3] == "start":
            self._call(lambda: self.store.start_workflow_run(actor_id, parts[2]))
            return

        self._json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

    def do_PATCH(self) -> None:
        path = urlparse(self.path).path
        try:
            body = self._body()
        except BadJSON:
            self._json({"error": "invalid_json"}, HTTPStatus.BAD_REQUEST)
            return
        parts = [part for part in path.split("/") if part]
        actor = actor_from_headers(self.headers)
        if not self._authorize(actor, "PATCH", path, body):
            return
        actor_id = actor.actor_id

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
        if len(parts) == 3 and parts[:2] == ["v1", "credentials"]:
            self._call(lambda: self.store.update_credential(actor_id, parts[2], body))
            return
        if len(parts) == 4 and parts[:3] == ["v1", "gitlab", "profiles"]:
            self._call(lambda: self.store.update_gitlab_profile(actor_id, parts[3], body))
            return
        if len(parts) == 3 and parts[:2] == ["v1", "agents"]:
            self._call(lambda: self.store.update_agent(actor_id, parts[2], body))
            return
        if len(parts) == 3 and parts[:2] == ["v1", "skills"]:
            self._call(lambda: self.store.update_skill(actor_id, parts[2], body))
            return
        if len(parts) == 3 and parts[:2] == ["v1", "model-providers"]:
            self._call(lambda: self.store.update_model_provider(actor_id, parts[2], body))
            return
        if len(parts) == 3 and parts[:2] == ["v1", "workflows"]:
            self._call(lambda: self.store.update_workflow(actor_id, parts[2], body))
            return
        if len(parts) == 5 and parts[:2] == ["v1", "workflows"] and parts[3] == "versions":
            self._call(lambda: self.store.update_workflow_version(actor_id, parts[2], parts[4], body))
            return
        if len(parts) == 3 and parts[:2] == ["v1", "test-runs"]:
            self._call(lambda: self.store.update_test_run(actor_id, parts[2], body))
            return
        if len(parts) == 5 and parts[:2] == ["v1", "workflow-runs"] and parts[3] == "steps":
            self._call(lambda: self.store.update_workflow_step_run(actor_id, parts[2], parts[4], body))
            return

        self._json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        actor = actor_from_headers(self.headers)
        if not self._authorize(actor, "DELETE", path):
            return
        actor_id = actor.actor_id
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
        if len(parts) == 3 and parts[:2] == ["v1", "credentials"]:
            self._call(lambda: self.store.delete_credential(actor_id, parts[2]))
            return
        if len(parts) == 4 and parts[:3] == ["v1", "gitlab", "profiles"]:
            self._call(lambda: self.store.delete_gitlab_profile(actor_id, parts[3]))
            return
        if len(parts) == 3 and parts[:2] == ["v1", "agents"]:
            self._call(lambda: self.store.delete_agent(actor_id, parts[2]))
            return
        if len(parts) == 3 and parts[:2] == ["v1", "skills"]:
            self._call(lambda: self.store.delete_skill(actor_id, parts[2]))
            return
        if len(parts) == 3 and parts[:2] == ["v1", "model-providers"]:
            self._call(lambda: self.store.delete_model_provider(actor_id, parts[2]))
            return
        if len(parts) == 3 and parts[:2] == ["v1", "workflows"]:
            self._call(lambda: self.store.delete_workflow(actor_id, parts[2]))
            return
        if len(parts) == 5 and parts[:2] == ["v1", "projects"] and parts[3] == "assets":
            self._call(lambda: self.store.unlink_project_asset(actor_id, parts[2], parts[4]))
            return
        if len(parts) == 5 and parts[:2] == ["v1", "projects"] and parts[3] == "environments":
            self._call(lambda: self.store.unlink_project_environment(actor_id, parts[2], parts[4]))
            return
        if len(parts) == 6 and parts[:2] == ["v1", "projects"] and parts[3] == "repositories":
            self._call(lambda: self.store.unlink_project_repository(actor_id, parts[2], parts[4], parts[5]))
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
        except (TypeError, ValueError):
            self._json({"error": "invalid_input"}, HTTPStatus.BAD_REQUEST)

    def _authorize(self, actor: Any, method: str, path: str, body: dict[str, Any] | None = None) -> bool:
        try:
            require_permission(actor, permission_for_request(method, path, body))
            return True
        except DomainError as exc:
            self._json({"error": exc.code}, exc.status)
            return False

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
        self.send_header("Access-Control-Allow-Headers", "Content-Type,X-Actor-ID,X-Actor-Role")


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
