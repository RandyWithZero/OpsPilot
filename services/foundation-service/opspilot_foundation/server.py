from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from .auth import (
    ROLE_ADMIN,
    ActorContext,
    AuthenticationRequired,
    PermissionDenied,
    actor_from_bearer_token,
    actor_from_headers,
    bearer_token_from_headers,
    dev_headers_enabled,
    dev_issuer_enabled,
    permission_for_request,
    require_permission,
)
from .domain import DomainError
from .store import foundation_store_from_env

MAX_REQUEST_BODY_BYTES = int(os.environ.get("OPSPILOT_MAX_REQUEST_BODY_BYTES", str(8 * 1024 * 1024)))


class FoundationHandler(BaseHTTPRequestHandler):
    store = foundation_store_from_env()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        routes: dict[str, Callable[[], Any]] = {
            "/healthz": self.store.health,
            "/readyz": self.store.diagnostics,
            "/v1/users": self.store.list_users,
            "/v1/projects": self.store.list_projects,
            "/v1/credentials": self.store.list_credentials,
            "/v1/gitlab/profiles": self.store.list_gitlab_profiles,
            "/v1/vcs/operations": self.store.list_vcs_operations,
            "/v1/vcs/webhook-events": self.store.list_vcs_webhook_events,
            "/v1/agents": self.store.list_agents,
            "/v1/skills": self.store.list_skills,
            "/v1/model-providers": self.store.list_model_providers,
            "/v1/ai/contracts": self.store.list_ai_prompt_contracts,
            "/v1/ai/runs": self.store.list_ai_run_traces,
            "/v1/workflows": self.store.list_workflows,
            "/v1/workflow-runs": self.store.list_workflow_runs,
            "/v1/runtime/tasks": self.store.list_runtime_tasks,
            "/v1/test-cases": self.store.list_test_cases,
            "/v1/test-suites": self.store.list_test_suites,
            "/v1/test-runs": self.store.list_test_runs,
            "/v1/reports": self.store.list_reports,
            "/v1/quality-gates": self.store.list_quality_gates,
            "/v1/audit-events": self.store.list_audit_events,
            "/v1/service-identities": self.store.list_service_identities,
        }
        parsed = urlparse(self.path)
        path = parsed.path
        actor = self._actor(path)
        if actor is None:
            return
        if not self._authorize(actor, "GET", path):
            return
        query = parse_qs(parsed.query)
        actor_id = actor.actor_id
        file_query = self._query_filters(parsed.query)
        parts = [part for part in path.split("/") if part]
        if path == "/v1/assets":
            self._call(lambda: self.store.list_assets(self._query_filters(parsed.query)))
            return
        if path == "/v1/environments":
            self._call(lambda: self.store.list_environments(self._query_filters(parsed.query)))
            return
        if path == "/v1/files":
            self._call(lambda: self.store.list_file_objects(self._file_access_filters(actor, file_query)))
            return
        if path == "/v1/runtime/tasks":
            self._call(lambda: self.store.list_runtime_tasks(first(query, "status")))
            return
        if len(parts) == 4 and parts[:2] == ["v1", "files"] and parts[3] == "download":
            self._call(lambda: self.store.download_file_object(actor_id, parts[2], self._file_access_filters(actor, file_query)))
            return
        if len(parts) == 5 and parts[:3] == ["v1", "gitlab", "profiles"] and parts[4] == "repositories":
            self._call(
                lambda: self.store.discover_gitlab_repositories(
                    parts[3],
                    search=first(query, "search"),
                    page=int(first(query, "page", "1")),
                    per_page=int(first(query, "per_page", "20")),
                )
            )
            return
        if len(parts) == 7 and parts[:3] == ["v1", "gitlab", "profiles"] and parts[4] == "repositories" and parts[6] == "branches":
            self._call(lambda: self.store.list_gitlab_branches(actor_id, first(query, "project_id"), parts[3], parts[5]))
            return
        if len(parts) == 8 and parts[:3] == ["v1", "gitlab", "profiles"] and parts[4] == "repositories" and parts[6] == "merge-requests":
            self._call(lambda: self.store.get_gitlab_merge_request(actor_id, first(query, "project_id"), parts[3], parts[5], parts[7]))
            return
        if len(parts) == 4 and parts[:2] == ["v1", "workflows"] and parts[3] == "versions":
            self._call(lambda: self.store.list_workflow_versions(parts[2]))
            return
        if len(parts) == 4 and parts[:2] == ["v1", "workflows"] and parts[3] == "runs":
            self._call(lambda: self.store.list_workflow_runs(parts[2]))
            return
        if len(parts) == 4 and parts[:3] == ["v1", "ai", "contracts"]:
            self._call(lambda: self.store.get_ai_prompt_contract(parts[3]))
            return
        if len(parts) == 4 and parts[:3] == ["v1", "ai", "runs"]:
            self._call(lambda: self.store.get_ai_run_trace(parts[3]))
            return
        if path == "/readyz":
            self._readyz()
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
        if path in {"/v1/auth/login", "/v1/auth/dev-token"}:
            if not dev_issuer_enabled():
                self._json({"error": "authentication_required"}, HTTPStatus.UNAUTHORIZED)
                return
            self._call(lambda: self.store.issue_dev_session(body), HTTPStatus.CREATED)
            return
        if path == "/v1/auth/refresh":
            self._call(lambda: self.store.refresh_session(body))
            return
        parts = [part for part in path.split("/") if part]
        if len(parts) == 4 and parts[:2] == ["v1", "service-identities"] and parts[3] == "token":
            self._call(lambda: self.store.issue_service_identity_token(parts[2], parts[2], body))
            return
        actor = self._actor(path)
        if actor is None:
            return
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
            self._call(lambda: self.store.create_file_object(actor_id, self._file_write_body(actor, body)), HTTPStatus.CREATED)
            return
        if path == "/v1/files/upload":
            self._call(lambda: self.store.upload_file_object(actor_id, self._file_write_body(actor, body)), HTTPStatus.CREATED)
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
            if self.headers.get("X-Gitlab-Token"):
                body["authenticity_token"] = self.headers.get("X-Gitlab-Token", "")
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
        if path == "/v1/ai/contracts":
            self._call(lambda: self.store.create_ai_prompt_contract(actor_id, body), HTTPStatus.CREATED)
            return
        if path == "/v1/ai/runs":
            self._call(lambda: self.store.create_ai_run_trace(actor_id, body), HTTPStatus.CREATED)
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
        if len(parts) == 4 and parts[:2] == ["v1", "test-runs"] and parts[3] == "artifacts":
            self._call(lambda: self.store.ingest_test_run_artifacts(actor_id, parts[2], body), HTTPStatus.CREATED)
            return
        if path == "/v1/runtime/tasks/claim":
            self._call(lambda: self.store.claim_runtime_task(actor_id, body))
            return
        if path == "/v1/auth/logout":
            self._call(lambda: self.store.logout_session(actor_id, {**body, "session_id": actor.session_id}))
            return
        if path == "/v1/service-identities":
            self._call(lambda: self.store.create_service_identity(actor_id, body), HTTPStatus.CREATED)
            return

        if len(parts) == 4 and parts[:2] == ["v1", "files"] and parts[3] == "upload-grants":
            self._call(lambda: self.store.create_upload_grant(actor_id, parts[2], self._file_access_filters(actor, {})), HTTPStatus.CREATED)
            return
        if len(parts) == 4 and parts[:2] == ["v1", "files"] and parts[3] == "upload-sessions":
            self._call(lambda: self.store.create_upload_session(actor_id, parts[2], self._file_access_filters(actor, {})), HTTPStatus.CREATED)
            return
        if len(parts) == 5 and parts[:3] == ["v1", "files", "upload-sessions"] and parts[4] == "complete":
            self._call(lambda: self.store.complete_upload_session(actor_id, parts[3], body, self._file_access_filters(actor, {})))
            return
        if len(parts) == 4 and parts[:2] == ["v1", "files"] and parts[3] == "download-grants":
            self._call(lambda: self.store.create_download_grant(actor_id, parts[2], self._file_access_filters(actor, {})), HTTPStatus.CREATED)
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
        if len(parts) == 5 and parts[:2] == ["v1", "environments"] and parts[3] == "assets":
            self._call(lambda: self.store.link_environment_asset(actor_id, parts[2], parts[4]))
            return
        if len(parts) == 5 and parts[:2] == ["v1", "environments"] and parts[3] == "members":
            self._call(lambda: self.store.link_environment_member(actor_id, parts[2], parts[4]))
            return
        if len(parts) == 5 and parts[:2] == ["v1", "environments"] and parts[3] == "files":
            self._call(lambda: self.store.link_environment_file(actor_id, parts[2], parts[4]))
            return
        if len(parts) == 4 and parts[:2] == ["v1", "workflows"] and parts[3] == "versions":
            self._call(lambda: self.store.create_workflow_version(actor_id, parts[2], body), HTTPStatus.CREATED)
            return
        if len(parts) == 6 and parts[:3] == ["v1", "gitlab", "profiles"] and parts[4] == "repositories" and parts[5] == "sync":
            self._call(lambda: self.store.sync_gitlab_repositories(actor_id, parts[3], search=str(body.get("search", "")), page=int(body.get("page", 1)), per_page=int(body.get("per_page", 20))))
            return
        if len(parts) == 7 and parts[:3] == ["v1", "gitlab", "profiles"] and parts[4] == "repositories" and parts[6] == "branches":
            self._call(lambda: self.store.create_gitlab_branch(actor_id, parts[3], parts[5], body), HTTPStatus.CREATED)
            return
        if len(parts) == 7 and parts[:3] == ["v1", "gitlab", "profiles"] and parts[4] == "repositories" and parts[6] == "merge-requests":
            self._call(lambda: self.store.create_gitlab_merge_request(actor_id, parts[3], parts[5], body), HTTPStatus.CREATED)
            return
        if len(parts) == 4 and parts[:2] == ["v1", "workflows"] and parts[3] == "runs":
            self._call(lambda: self.store.create_workflow_run(actor_id, parts[2], body), HTTPStatus.CREATED)
            return
        if len(parts) == 4 and parts[:2] == ["v1", "workflow-runs"] and parts[3] == "start":
            self._call(lambda: self.store.start_workflow_run(actor_id, parts[2]))
            return
        if len(parts) == 4 and parts[:2] == ["v1", "workflow-runs"] and parts[3] == "cancel":
            self._call(lambda: self.store.cancel_workflow_run(actor_id, parts[2]))
            return
        if len(parts) == 5 and parts[:3] == ["v1", "runtime", "tasks"] and parts[4] == "callback":
            self._call(lambda: self.store.callback_runtime_task(actor_id, parts[3], body))
            return
        if len(parts) == 5 and parts[:3] == ["v1", "runtime", "tasks"] and parts[4] == "timeout":
            self._call(lambda: self.store.timeout_runtime_task(actor_id, parts[3]))
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
        actor = self._actor(path)
        if actor is None:
            return
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
        actor = self._actor(path)
        if actor is None:
            return
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
        if len(parts) == 3 and parts[:2] == ["v1", "files"]:
            query = self._query_filters(urlparse(self.path).query)
            self._call(lambda: self.store.delete_file_object(actor_id, parts[2], self._file_access_filters(actor, query)))
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
        if len(parts) == 3 and parts[:2] == ["v1", "service-identities"]:
            self._call(lambda: self.store.revoke_service_identity(actor_id, parts[2]))
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
        if len(parts) == 5 and parts[:2] == ["v1", "environments"] and parts[3] == "assets":
            self._call(lambda: self.store.unlink_environment_asset(actor_id, parts[2], parts[4]))
            return
        if len(parts) == 5 and parts[:2] == ["v1", "environments"] and parts[3] == "members":
            self._call(lambda: self.store.unlink_environment_member(actor_id, parts[2], parts[4]))
            return
        if len(parts) == 5 and parts[:2] == ["v1", "environments"] and parts[3] == "files":
            self._call(lambda: self.store.unlink_environment_file(actor_id, parts[2], parts[4]))
            return

        self._json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _body(self) -> dict[str, Any]:
        size = int(self.headers.get("Content-Length", "0"))
        if size > MAX_REQUEST_BODY_BYTES:
            raise BadJSON("request body is too large")
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

    def _readyz(self) -> None:
        try:
            payload = self.store.diagnostics()
            status = HTTPStatus.OK if payload.get("status") == "ok" else HTTPStatus.SERVICE_UNAVAILABLE
            self._json(payload, status)
        except (TypeError, ValueError):
            self._json({"error": "invalid_input"}, HTTPStatus.BAD_REQUEST)

    def _authorize(self, actor: Any, method: str, path: str, body: dict[str, Any] | None = None) -> bool:
        try:
            require_permission(actor, permission_for_request(method, path, body))
            return True
        except DomainError as exc:
            self._json({"error": exc.code}, exc.status)
            return False

    def _actor(self, path: str) -> ActorContext | None:
        if path in {"/healthz", "/readyz"}:
            return ActorContext(actor_id="system", role=ROLE_ADMIN)
        try:
            if dev_headers_enabled() and (self.headers.get("X-Actor-ID") or self.headers.get("X-Actor-Role")):
                return actor_from_headers(self.headers)
            return self.store.validate_actor_session(actor_from_bearer_token(bearer_token_from_headers(self.headers)))
        except (AuthenticationRequired, RuntimeError) as exc:
            code = exc.code if isinstance(exc, AuthenticationRequired) else "authentication_required"
            self._json({"error": code}, HTTPStatus.UNAUTHORIZED)
            return None

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
        self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization,X-Actor-ID,X-Actor-Role,X-Gitlab-Token")

    def _query_filters(self, query: str) -> dict[str, str]:
        filters: dict[str, str] = {}
        for key, values in parse_qs(query, keep_blank_values=False).items():
            if values:
                filters[key] = values[-1]
        return filters

    def _file_access_filters(self, actor: ActorContext, filters: dict[str, str]) -> dict[str, str]:
        scoped = dict(filters)
        if actor.role == ROLE_ADMIN:
            return scoped
        requested_owner = scoped.get("owner_id")
        if requested_owner and requested_owner != actor.actor_id:
            raise PermissionDenied("actor cannot access files for another owner")
        scoped["owner_id"] = actor.actor_id
        return scoped

    def _file_write_body(self, actor: ActorContext, body: dict[str, Any]) -> dict[str, Any]:
        scoped = dict(body)
        requested_owner = str(scoped.get("owner_id", "") or "")
        if actor.role != ROLE_ADMIN and requested_owner and requested_owner != actor.actor_id:
            raise PermissionDenied("actor cannot create files for another owner")
        scoped["owner_id"] = requested_owner or actor.actor_id
        return scoped


class BadJSON(Exception):
    pass


def first(query: dict[str, list[str]], key: str, default: str = "") -> str:
    values = query.get(key)
    return values[0] if values else default


def run() -> None:
    addr = os.environ.get("HTTP_ADDR", "0.0.0.0:8080")
    host, port = addr.rsplit(":", 1)
    server = ThreadingHTTPServer((host, int(port)), FoundationHandler)
    print(f"foundation-service listening on {addr}")
    server.serve_forever()


if __name__ == "__main__":
    run()
