from __future__ import annotations

import importlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlparse

from .domain import (
    Agent,
    Asset,
    AuditEvent,
    CredentialReference,
    Environment,
    FileObject,
    GitLabProfile,
    ModelProvider,
    Project,
    QualityGate,
    Report,
    Skill,
    TestCase,
    TestRun,
    TestSuite,
    UploadSession,
    User,
    VCSOperation,
    VCSWebhookEvent,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowStepRun,
    WorkflowVersion,
)
from .storage import ObjectStorage
from .store import MemoryStore


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations" / "mysql"


ENTITY_MODELS: list[tuple[str, str, type[Any]]] = [
    ("users", "users", User),
    ("projects", "projects", Project),
    ("assets", "assets", Asset),
    ("environments", "environments", Environment),
    ("files", "files", FileObject),
    ("upload_sessions", "upload_sessions", UploadSession),
    ("credentials", "credentials", CredentialReference),
    ("gitlab_profiles", "gitlab_profiles", GitLabProfile),
    ("vcs_operations", "vcs_operations", VCSOperation),
    ("vcs_webhook_events", "vcs_webhook_events", VCSWebhookEvent),
    ("agents", "agents", Agent),
    ("skills", "skills", Skill),
    ("model_providers", "model_providers", ModelProvider),
    ("workflows", "workflows", WorkflowDefinition),
    ("workflow_versions", "workflow_versions", WorkflowVersion),
    ("workflow_runs", "workflow_runs", WorkflowRun),
    ("workflow_step_runs", "workflow_step_runs", WorkflowStepRun),
    ("test_cases", "test_cases", TestCase),
    ("test_suites", "test_suites", TestSuite),
    ("test_runs", "test_runs", TestRun),
    ("reports", "reports", Report),
    ("quality_gates", "quality_gates", QualityGate),
]


MUTATING_METHODS = {
    "create_user",
    "update_user",
    "delete_user",
    "create_project",
    "update_project",
    "delete_project",
    "link_project_asset",
    "unlink_project_asset",
    "link_project_environment",
    "unlink_project_environment",
    "link_project_repository",
    "unlink_project_repository",
    "create_asset",
    "update_asset",
    "delete_asset",
    "create_environment",
    "update_environment",
    "delete_environment",
    "create_file_object",
    "upload_file_object",
    "download_file_object",
    "delete_file_object",
    "create_upload_grant",
    "create_upload_session",
    "complete_upload_session",
    "create_download_grant",
    "create_credential",
    "update_credential",
    "delete_credential",
    "create_gitlab_profile",
    "update_gitlab_profile",
    "delete_gitlab_profile",
    "sync_gitlab_repositories",
    "list_gitlab_branches",
    "create_gitlab_branch",
    "create_gitlab_merge_request",
    "get_gitlab_merge_request",
    "create_vcs_operation",
    "ingest_vcs_webhook_event",
    "create_agent",
    "update_agent",
    "delete_agent",
    "create_skill",
    "update_skill",
    "delete_skill",
    "create_model_provider",
    "update_model_provider",
    "delete_model_provider",
    "create_workflow",
    "update_workflow",
    "delete_workflow",
    "create_workflow_version",
    "update_workflow_version",
    "create_workflow_run",
    "start_workflow_run",
    "update_workflow_step_run",
    "create_test_case",
    "create_test_suite",
    "create_test_run",
    "update_test_run",
    "create_report",
    "create_quality_gate",
}


class MySQLStore(MemoryStore):
    def __init__(
        self,
        dsn: str,
        storage: ObjectStorage | None = None,
        gitlab_client: Any | None = None,
        connection_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._dsn = dsn
        self._connection_factory = connection_factory or self._build_connection_factory(dsn)
        super().__init__(storage=storage, gitlab_client=gitlab_client)
        self._apply_migrations()
        self._load_snapshot()

    def __getattribute__(self, name: str) -> Any:
        attr = super().__getattribute__(name)
        if name in MUTATING_METHODS and callable(attr):
            def persisted(*args: Any, **kwargs: Any) -> Any:
                result = attr(*args, **kwargs)
                self._persist_snapshot()
                return result
            return persisted
        return attr

    def health(self) -> dict[str, str]:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
        return {"status": "ok", "store": "mysql"}

    def _build_connection_factory(self, dsn: str) -> Callable[[], Any]:
        try:
            pymysql = importlib.import_module("pymysql")
        except ImportError as exc:
            raise RuntimeError("OPSPILOT_FOUNDATION_MYSQL_DSN requires the optional pymysql package") from exc
        parsed = urlparse(dsn)
        if parsed.scheme not in {"mysql", "mysql+pymysql"} or not parsed.hostname or not parsed.path.strip("/"):
            raise RuntimeError("OPSPILOT_FOUNDATION_MYSQL_DSN must look like mysql://user:pass@host:3306/database")
        return lambda: pymysql.connect(
            host=parsed.hostname,
            port=parsed.port or 3306,
            user=unquote(parsed.username or ""),
            password=unquote(parsed.password or ""),
            database=parsed.path.strip("/"),
            autocommit=False,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )

    def _connect(self) -> Any:
        return self._connection_factory()

    def _apply_migrations(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "CREATE TABLE IF NOT EXISTS foundation_schema_migrations ("
                    "version VARCHAR(128) NOT NULL PRIMARY KEY,"
                    "applied_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)"
                    ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci"
                )
                cursor.execute("SELECT version FROM foundation_schema_migrations")
                applied = {str(row["version"]) for row in cursor.fetchall()}
                for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                    if path.name in applied:
                        continue
                    for statement in _sql_statements(path.read_text(encoding="utf-8")):
                        cursor.execute(statement)
                    cursor.execute("INSERT INTO foundation_schema_migrations (version) VALUES (%s)", (path.name,))
            conn.commit()

    def _load_snapshot(self) -> None:
        with self._lock:
            with self._connect() as conn:
                with conn.cursor() as cursor:
                    for attr, table, model in ENTITY_MODELS:
                        cursor.execute(f"SELECT payload FROM {table} ORDER BY created_at, id")
                        setattr(self, attr, {row_id(row): model(**payload(row)) for row in cursor.fetchall()})
                    cursor.execute("SELECT payload FROM audit_events ORDER BY occurred_at, id")
                    self.audit_events = [AuditEvent(**payload(row)) for row in cursor.fetchall()]
                    cursor.execute("SELECT secret_ref, secret_value FROM secret_refs")
                    self.secret_store._vault = {str(row["secret_ref"]): str(row["secret_value"]) for row in cursor.fetchall()}
            self._ids = self._max_loaded_id()

    def _persist_snapshot(self) -> None:
        with self._lock:
            with self._connect() as conn:
                with conn.cursor() as cursor:
                    self._delete_snapshot(cursor)
                    self._insert_entities(cursor)
                    self._insert_relationships(cursor)
                    self._insert_secret_refs(cursor)
                conn.commit()

    def _delete_snapshot(self, cursor: Any) -> None:
        for table in [
            "audit_events",
            "quality_gates",
            "reports",
            "test_runs",
            "test_suite_cases",
            "test_suites",
            "test_cases",
            "workflow_step_runs",
            "workflow_runs",
            "workflow_versions",
            "workflows",
            "vcs_webhook_events",
            "vcs_operations",
            "agent_skills",
            "agents",
            "skills",
            "model_providers",
            "project_repository_bindings",
            "gitlab_profiles",
            "secret_refs",
            "credentials",
            "upload_sessions",
            "files",
            "environment_assets",
            "environment_members",
            "project_environments",
            "project_assets",
            "environments",
            "assets",
            "project_members",
            "projects",
            "users",
        ]:
            cursor.execute(f"DELETE FROM {table}")

    def _insert_entities(self, cursor: Any) -> None:
        for user in self.users.values():
            self._insert_payload(cursor, "users", ["id", "email", "name", "status", "roles", "created_at", "updated_at"], user)
        for project in self.projects.values():
            self._insert_payload(cursor, "projects", ["id", ("project_key", "key"), "name", "owner_id", "status", "created_at", "updated_at"], project)
        for asset in self.assets.values():
            self._insert_payload(cursor, "assets", ["id", "category", "name", "status", "owner_id", "parent_id", "created_at", "updated_at"], asset)
        for environment in self.environments.values():
            self._insert_payload(cursor, "environments", ["id", "project_id", "name", ("environment_type", "type"), "owner_id", "status", "created_at", "updated_at"], environment)
        for file_object in self.files.values():
            self._insert_payload(cursor, "files", ["id", "filename", "content_type", "size_bytes", "owner_id", "resource_type", "resource_id", "module", "status", "created_at", "updated_at"], file_object)
        for session in self.upload_sessions.values():
            self._insert_payload(cursor, "upload_sessions", ["id", "file_id", "status", "created_at", "updated_at"], session)
        for credential in self.credentials.values():
            self._insert_payload(cursor, "credentials", ["id", "provider", "name", "secret_ref", "secret_fingerprint", "status", "created_at", "updated_at"], credential)
        for profile in self.gitlab_profiles.values():
            self._insert_payload(cursor, "gitlab_profiles", ["id", "name", "base_url", "credential_ref_id", "status", "created_at", "updated_at"], profile)
        for provider in self.model_providers.values():
            self._insert_payload(cursor, "model_providers", ["id", "provider", "name", "credential_ref_id", "status", "created_at", "updated_at"], provider)
        for skill in self.skills.values():
            self._insert_payload(cursor, "skills", ["id", "name", "version", "runtime", "package_file_id", "status", "created_at", "updated_at"], skill)
        for agent in self.agents.values():
            self._insert_payload(cursor, "agents", ["id", "name", "kind", "model_provider_id", "status", "created_at", "updated_at"], agent)
        for workflow in self.workflows.values():
            self._insert_payload(cursor, "workflows", ["id", "name", "project_id", "active_version_id", "status", "created_at", "updated_at"], workflow)
        for version in self.workflow_versions.values():
            self._insert_payload(cursor, "workflow_versions", ["id", "workflow_id", "version", "status", "created_at", "updated_at"], version)
        for run in self.workflow_runs.values():
            self._insert_payload(cursor, "workflow_runs", ["id", "workflow_id", "workflow_version_id", "trigger_type", "status", "created_at", "updated_at"], run)
        for step in self.workflow_step_runs.values():
            self._insert_payload(cursor, "workflow_step_runs", ["id", "workflow_run_id", "workflow_id", "workflow_version_id", "node_id", "step_type", "sequence", "status", "predecessor_node_ids", "created_at", "updated_at"], step)
        for operation in self.vcs_operations.values():
            self._insert_payload(cursor, "vcs_operations", ["id", "provider", "profile_id", "repository_id", "operation_type", "status", "created_at", "updated_at"], operation)
        for event in self.vcs_webhook_events.values():
            self._insert_payload(cursor, "vcs_webhook_events", ["id", "provider", "profile_id", "repository_id", "event_type", "status", "created_at", "updated_at"], event)
        for case in self.test_cases.values():
            self._insert_payload(cursor, "test_cases", ["id", "project_id", "name", "case_type", "status", "created_at", "updated_at"], case)
        for suite in self.test_suites.values():
            self._insert_payload(cursor, "test_suites", ["id", "project_id", "name", "status", "created_at", "updated_at"], suite)
        for run in self.test_runs.values():
            self._insert_payload(cursor, "test_runs", ["id", "project_id", "suite_id", "environment_id", "status", "created_at", "updated_at"], run)
        for report in self.reports.values():
            self._insert_payload(cursor, "reports", ["id", "project_id", "report_type", "test_run_id", "status", "created_at", "updated_at"], report)
        for gate in self.quality_gates.values():
            self._insert_payload(cursor, "quality_gates", ["id", "project_id", "last_report_id", "status", "created_at", "updated_at"], gate)
        for event in self.audit_events:
            self._insert_payload(cursor, "audit_events", ["id", "actor_id", "action", "resource_type", "resource_id", "occurred_at", "metadata"], event)

    def _insert_relationships(self, cursor: Any) -> None:
        for project in self.projects.values():
            for user_id in project.member_ids:
                self._insert_row(cursor, "project_members", {"project_id": project.id, "user_id": user_id})
            for asset_id in project.asset_ids:
                self._insert_row(cursor, "project_assets", {"project_id": project.id, "asset_id": asset_id})
            for environment_id in project.environment_ids:
                self._insert_row(cursor, "project_environments", {"project_id": project.id, "environment_id": environment_id})
            for binding in project.repository_bindings:
                self._insert_row(cursor, "project_repository_bindings", {"project_id": project.id, **binding})
        for environment in self.environments.values():
            for user_id in environment.member_ids:
                self._insert_row(cursor, "environment_members", {"environment_id": environment.id, "user_id": user_id})
            for asset_id in environment.asset_ids:
                self._insert_row(cursor, "environment_assets", {"environment_id": environment.id, "asset_id": asset_id})
        for agent in self.agents.values():
            for skill_id in agent.skill_ids:
                self._insert_row(cursor, "agent_skills", {"agent_id": agent.id, "skill_id": skill_id})
        for suite in self.test_suites.values():
            for case_id in suite.case_ids:
                self._insert_row(cursor, "test_suite_cases", {"suite_id": suite.id, "case_id": case_id})

    def _insert_secret_refs(self, cursor: Any) -> None:
        for secret_ref, secret_value in self.secret_store._vault.items():
            self._insert_row(cursor, "secret_refs", {"secret_ref": secret_ref, "secret_value": secret_value})

    def _insert_payload(self, cursor: Any, table: str, columns: list[str | tuple[str, str]], entity: Any) -> None:
        payload_value = asdict(entity)
        row = {"payload": json.dumps(payload_value, separators=(",", ":"), sort_keys=True)}
        for column in columns:
            column_name, field_name = column if isinstance(column, tuple) else (column, column)
            value = payload_value[field_name]
            row[column_name] = json.dumps(value, separators=(",", ":"), sort_keys=True) if isinstance(value, (dict, list)) else value
        self._insert_row(cursor, table, row)

    def _insert_row(self, cursor: Any, table: str, row: dict[str, Any]) -> None:
        columns = list(row)
        placeholders = ", ".join(["%s"] * len(columns))
        names = ", ".join(columns)
        cursor.execute(f"INSERT INTO {table} ({names}) VALUES ({placeholders})", tuple(row[column] for column in columns))

    def _max_loaded_id(self) -> int:
        max_id = 0
        ids: list[str] = []
        for attr, _, _ in ENTITY_MODELS:
            ids.extend(getattr(self, attr).keys())
        ids.extend(event.id for event in self.audit_events)
        for value in ids:
            suffix = value.rsplit("_", 1)[-1]
            if suffix.isdigit():
                max_id = max(max_id, int(suffix))
        return max_id


def _sql_statements(sql: str) -> list[str]:
    return [statement.strip() for statement in sql.split(";") if statement.strip()]


def payload(row: dict[str, Any]) -> dict[str, Any]:
    value = row["payload"]
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    return json.loads(value) if isinstance(value, str) else dict(value)


def row_id(row: dict[str, Any]) -> str:
    return str(payload(row)["id"])
