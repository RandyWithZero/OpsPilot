from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlsplit, urlunsplit


class DomainError(Exception):
    code = "domain_error"
    status = 400


class InvalidInput(DomainError):
    code = "invalid_input"
    status = 400


class NotFound(DomainError):
    code = "not_found"
    status = 404


class Conflict(DomainError):
    code = "conflict"
    status = 409


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Role:
    scope: str
    name: str


@dataclass
class User:
    email: str
    name: str
    roles: list[dict[str, str]] = field(default_factory=list)
    id: str = ""
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""

    def validate(self) -> None:
        if not self.email or "@" not in self.email or not self.name:
            raise InvalidInput("users require email and name")


@dataclass
class Project:
    key: str
    name: str
    owner_id: str
    description: str = ""
    member_ids: list[str] = field(default_factory=list)
    asset_ids: list[str] = field(default_factory=list)
    environment_ids: list[str] = field(default_factory=list)
    repository_bindings: list[dict[str, str]] = field(default_factory=list)
    id: str = ""
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""

    def validate(self) -> None:
        if not self.key or not self.name or not self.owner_id:
            raise InvalidInput("projects require key, name, and owner_id")


@dataclass
class Asset:
    category: str
    name: str
    status: str = "available"
    owner_id: str = ""
    location: str = ""
    parent_id: str = ""
    capabilities: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    file_ids: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    id: str = ""
    created_at: str = ""
    updated_at: str = ""

    def validate(self) -> None:
        if not self.category or not self.name:
            raise InvalidInput("assets require category and name")


@dataclass
class Endpoint:
    name: str
    url: str


@dataclass
class Environment:
    project_id: str
    name: str
    type: str
    owner_id: str
    status: str = "active"
    member_ids: list[str] = field(default_factory=list)
    asset_ids: list[str] = field(default_factory=list)
    endpoints: list[dict[str, str]] = field(default_factory=list)
    file_ids: list[str] = field(default_factory=list)
    id: str = ""
    created_at: str = ""
    updated_at: str = ""

    def validate(self) -> None:
        if not self.project_id or not self.name or not self.owner_id:
            raise InvalidInput("environments require project_id, name, and owner_id")
        if self.type not in {"DEV", "QA", "QE"}:
            raise InvalidInput("environment type must be DEV, QA, or QE")


@dataclass
class FileObject:
    filename: str
    content_type: str
    size_bytes: int
    owner_id: str = ""
    resource_type: str = ""
    resource_id: str = ""
    module: str = ""
    storage_key: str = ""
    status: str = "pending_upload"
    checksum: str = ""
    id: str = ""
    created_at: str = ""
    updated_at: str = ""
    deleted_at: str = ""
    deleted_by: str = ""

    def validate(self) -> None:
        self.filename = sanitize_filename(self.filename)
        if not self.filename or not self.content_type or int(self.size_bytes) < 0:
            raise InvalidInput("files require filename, content_type, and non-negative size_bytes")
        if self.status not in {"pending_upload", "available", "deleted"}:
            raise InvalidInput("file status must be pending_upload, available, or deleted")
        self.resource_type = sanitize_token(self.resource_type, "resource_type", allow_empty=True)
        self.resource_id = sanitize_token(self.resource_id, "resource_id", allow_empty=True)
        self.module = sanitize_token(self.module, "module", allow_empty=True)


@dataclass
class UploadSession:
    file_id: str
    method: str = "PUT"
    status: str = "open"
    url: str = ""
    expires_in_seconds: int = 900
    id: str = ""
    created_at: str = ""
    updated_at: str = ""

    def validate(self) -> None:
        if not self.file_id:
            raise InvalidInput("upload sessions require file_id")
        if self.method != "PUT":
            raise InvalidInput("upload session method must be PUT")
        if self.status not in {"open", "completed", "cancelled"}:
            raise InvalidInput("upload session status must be open, completed, or cancelled")
        if int(self.expires_in_seconds) <= 0:
            raise InvalidInput("upload sessions require a positive expires_in_seconds")


@dataclass
class CredentialReference:
    provider: str
    name: str
    secret_ref: str = ""
    secret_fingerprint: str = ""
    status: str = "active"
    id: str = ""
    created_at: str = ""
    updated_at: str = ""

    def validate(self) -> None:
        if not self.provider or not self.name:
            raise InvalidInput("credentials require provider and name")


@dataclass
class GitLabProfile:
    name: str
    base_url: str
    credential_ref_id: str
    repository_selection: list[dict[str, str]] = field(default_factory=list)
    repository_synced_at: str = ""
    webhook_secret_ref: str = ""
    id: str = ""
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""

    def validate(self) -> None:
        if not self.name or not self.base_url or not self.credential_ref_id:
            raise InvalidInput("gitlab profiles require name, base_url, and credential_ref_id")
        self.base_url = sanitize_public_url(self.base_url, allow_path=False)


@dataclass
class RepositoryBinding:
    provider: str
    profile_id: str
    repository_id: str

    def validate(self) -> None:
        if not self.provider or not self.profile_id or not self.repository_id:
            raise InvalidInput("repository bindings require provider, profile_id, and repository_id")


@dataclass
class VCSOperation:
    provider: str
    profile_id: str
    repository_id: str
    operation_type: str
    branch: str = ""
    source_branch: str = ""
    target_branch: str = ""
    title: str = ""
    status: str = "queued"
    external_id: str = ""
    result: dict[str, Any] = field(default_factory=dict)
    id: str = ""
    created_at: str = ""
    updated_at: str = ""

    def validate(self) -> None:
        if self.provider != "gitlab":
            raise InvalidInput("only gitlab VCS operations are supported")
        if not self.profile_id or not self.repository_id or not self.operation_type:
            raise InvalidInput("VCS operations require profile_id, repository_id, and operation_type")
        if self.operation_type not in {"create_branch", "open_merge_request", "merge_merge_request", "read_branches", "read_merge_request"}:
            raise InvalidInput("unsupported VCS operation_type")
        if self.status not in {"queued", "completed", "failed"}:
            raise InvalidInput("VCS operation status must be queued, completed, or failed")
        if self.operation_type == "create_branch" and not self.branch:
            raise InvalidInput("create_branch operations require branch")
        if self.operation_type == "open_merge_request" and (not self.source_branch or not self.target_branch or not self.title):
            raise InvalidInput("open_merge_request operations require source_branch, target_branch, and title")
        if self.operation_type == "merge_merge_request" and not self.external_id:
            raise InvalidInput("merge_merge_request operations require external_id")


@dataclass
class VCSWebhookEvent:
    provider: str
    profile_id: str
    event_type: str
    repository_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    status: str = "received"
    id: str = ""
    created_at: str = ""
    updated_at: str = ""

    def validate(self) -> None:
        if self.provider != "gitlab":
            raise InvalidInput("only gitlab webhook events are supported")
        if not self.profile_id or not self.event_type:
            raise InvalidInput("webhook events require profile_id and event_type")
        if self.status not in {"received", "processed", "rejected"}:
            raise InvalidInput("webhook event status must be received, processed, or rejected")


@dataclass
class Agent:
    name: str
    kind: str
    description: str = ""
    status: str = "active"
    capabilities: list[str] = field(default_factory=list)
    skill_ids: list[str] = field(default_factory=list)
    model_provider_id: str = ""
    id: str = ""
    created_at: str = ""
    updated_at: str = ""

    def validate(self) -> None:
        if not self.name or not self.kind:
            raise InvalidInput("agents require name and kind")


@dataclass
class Skill:
    name: str
    version: str
    runtime: str
    description: str = ""
    status: str = "active"
    capabilities: list[str] = field(default_factory=list)
    package_file_id: str = ""
    id: str = ""
    created_at: str = ""
    updated_at: str = ""

    def validate(self) -> None:
        if not self.name or not self.version or not self.runtime:
            raise InvalidInput("skills require name, version, and runtime")


@dataclass
class ModelProvider:
    provider: str
    name: str
    credential_ref_id: str
    base_url: str = ""
    models: list[str] = field(default_factory=list)
    status: str = "active"
    id: str = ""
    created_at: str = ""
    updated_at: str = ""

    def validate(self) -> None:
        if not self.provider or not self.name or not self.credential_ref_id:
            raise InvalidInput("model providers require provider, name, and credential_ref_id")
        if self.base_url:
            self.base_url = sanitize_public_url(self.base_url, allow_path=True)


@dataclass
class WorkflowDefinition:
    name: str
    description: str = ""
    project_id: str = ""
    status: str = "draft"
    active_version_id: str = ""
    id: str = ""
    created_at: str = ""
    updated_at: str = ""

    def validate(self) -> None:
        if not self.name:
            raise InvalidInput("workflows require name")


@dataclass
class WorkflowVersion:
    workflow_id: str
    version: str
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    status: str = "draft"
    id: str = ""
    created_at: str = ""
    updated_at: str = ""

    def validate(self) -> None:
        if not self.workflow_id or not self.version:
            raise InvalidInput("workflow versions require workflow_id and version")
        node_ids = set()
        for node in self.nodes:
            node_id = str(node.get("id", "")).strip()
            node_type = str(node.get("type", "")).strip()
            if not node_id or not node_type:
                raise InvalidInput("workflow nodes require id and type")
            if node_id in node_ids:
                raise Conflict("workflow node ids must be unique")
            node_ids.add(node_id)
        for edge in self.edges:
            if edge.get("from_node_id") not in node_ids or edge.get("to_node_id") not in node_ids:
                raise InvalidInput("workflow edges must reference existing nodes")


@dataclass
class WorkflowRun:
    workflow_id: str
    workflow_version_id: str
    trigger_type: str = "manual"
    status: str = "created"
    id: str = ""
    started_at: str = ""
    completed_at: str = ""
    created_at: str = ""
    updated_at: str = ""

    def validate(self) -> None:
        if not self.workflow_id or not self.workflow_version_id:
            raise InvalidInput("workflow runs require workflow_id and workflow_version_id")
        if self.trigger_type not in {"manual"}:
            raise InvalidInput("workflow run trigger_type must be manual")
        if self.status not in {"created", "running", "completed", "failed", "cancelled"}:
            raise InvalidInput("workflow run status must be created, running, completed, failed, or cancelled")


@dataclass
class WorkflowStepRun:
    workflow_run_id: str
    workflow_id: str
    workflow_version_id: str
    node_id: str
    node_type: str
    step_type: str
    sequence: int
    name: str = ""
    status: str = "pending"
    agent_id: str = ""
    skill_id: str = ""
    model_provider_id: str = ""
    predecessor_node_ids: list[str] = field(default_factory=list)
    input: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    id: str = ""
    started_at: str = ""
    completed_at: str = ""
    created_at: str = ""
    updated_at: str = ""

    def validate(self) -> None:
        if not self.workflow_run_id or not self.workflow_id or not self.workflow_version_id or not self.node_id or not self.node_type:
            raise InvalidInput("workflow step runs require run, workflow, version, node_id, and node_type")
        if self.step_type not in {"trigger", "agent", "manual", "result"}:
            raise InvalidInput("workflow step run step_type must be trigger, agent, manual, or result")
        if self.status not in {"pending", "running", "completed", "failed", "skipped"}:
            raise InvalidInput("workflow step run status must be pending, running, completed, failed, or skipped")


@dataclass
class WorkflowRuntimeTask:
    workflow_run_id: str
    workflow_step_run_id: str
    workflow_id: str
    workflow_version_id: str
    node_id: str
    agent_id: str
    skill_id: str = ""
    model_provider_id: str = ""
    status: str = "queued"
    attempt: int = 1
    max_attempts: int = 1
    attempt_token: str = ""
    input_summary: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    timeout_seconds: int = 0
    id: str = ""
    claimed_at: str = ""
    completed_at: str = ""
    created_at: str = ""
    updated_at: str = ""

    def validate(self) -> None:
        if not self.workflow_run_id or not self.workflow_step_run_id or not self.workflow_id or not self.workflow_version_id or not self.node_id:
            raise InvalidInput("runtime tasks require workflow run, step run, workflow, version, and node_id")
        if not self.agent_id:
            raise InvalidInput("runtime tasks require agent_id")
        if self.status not in {"queued", "running", "completed", "failed", "cancelled", "timed_out"}:
            raise InvalidInput("runtime task status must be queued, running, completed, failed, cancelled, or timed_out")
        if int(self.attempt) <= 0 or int(self.max_attempts) <= 0:
            raise InvalidInput("runtime task attempts must be positive")
        if int(self.timeout_seconds) < 0:
            raise InvalidInput("runtime task timeout_seconds must not be negative")


@dataclass
class TestCase:
    project_id: str
    name: str
    case_type: str = "manual"
    priority: str = "medium"
    status: str = "active"
    steps: list[dict[str, Any]] = field(default_factory=list)
    id: str = ""
    created_at: str = ""
    updated_at: str = ""

    def validate(self) -> None:
        if not self.project_id or not self.name:
            raise InvalidInput("test cases require project_id and name")
        if self.case_type not in {"manual", "automated"}:
            raise InvalidInput("test case case_type must be manual or automated")


@dataclass
class TestSuite:
    project_id: str
    name: str
    case_ids: list[str] = field(default_factory=list)
    status: str = "active"
    id: str = ""
    created_at: str = ""
    updated_at: str = ""

    def validate(self) -> None:
        if not self.project_id or not self.name:
            raise InvalidInput("test suites require project_id and name")


@dataclass
class TestRun:
    project_id: str
    suite_id: str
    environment_id: str = ""
    status: str = "queued"
    results: list[dict[str, Any]] = field(default_factory=list)
    id: str = ""
    created_at: str = ""
    updated_at: str = ""

    def validate(self) -> None:
        if not self.project_id or not self.suite_id:
            raise InvalidInput("test runs require project_id and suite_id")
        if self.status not in {"queued", "running", "passed", "failed", "cancelled"}:
            raise InvalidInput("test run status must be queued, running, passed, failed, or cancelled")


@dataclass
class Report:
    project_id: str
    title: str
    report_type: str = "test"
    test_run_id: str = ""
    file_ids: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    status: str = "draft"
    id: str = ""
    created_at: str = ""
    updated_at: str = ""

    def validate(self) -> None:
        if not self.project_id or not self.title:
            raise InvalidInput("reports require project_id and title")
        if self.report_type not in {"test", "qa", "qe", "operations"}:
            raise InvalidInput("unsupported report_type")


@dataclass
class QualityGate:
    project_id: str
    name: str
    conditions: list[dict[str, Any]] = field(default_factory=list)
    last_report_id: str = ""
    status: str = "pending"
    id: str = ""
    created_at: str = ""
    updated_at: str = ""

    def validate(self) -> None:
        if not self.project_id or not self.name:
            raise InvalidInput("quality gates require project_id and name")
        if self.status not in {"pending", "passed", "failed", "waived"}:
            raise InvalidInput("quality gate status must be pending, passed, failed, or waived")


@dataclass
class AuditEvent:
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = ""
    occurred_at: str = ""


TOKEN_QUERY_NAMES = {"access_token", "auth_token", "api_token", "private_token", "token", "key", "secret", "password"}
SENSITIVE_FIELD_NAMES = TOKEN_QUERY_NAMES | {"authorization", "cookie", "set-cookie", "x-gitlab-token"}


def sanitize_filename(value: str) -> str:
    filename = str(value).strip()
    if not filename or filename in {".", ".."}:
        raise InvalidInput("filename is invalid")
    if "/" in filename or "\\" in filename:
        raise InvalidInput("filename must not contain path separators")
    if any(ord(character) < 32 for character in filename):
        raise InvalidInput("filename must not contain control characters")
    return filename


def sanitize_token(value: str, label: str, *, allow_empty: bool) -> str:
    token = str(value).strip()
    if not token and allow_empty:
        return ""
    if not token:
        raise InvalidInput(f"{label} is required")
    if any(ord(character) < 32 for character in token):
        raise InvalidInput(f"{label} must not contain control characters")
    if "/" in token or "\\" in token:
        raise InvalidInput(f"{label} must not contain path separators")
    return token


def redact_sensitive_payload(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_string = str(key)
            key_lower = key_string.lower()
            if key_lower in SENSITIVE_FIELD_NAMES or "token" in key_lower or "secret" in key_lower or "password" in key_lower or "key" in key_lower:
                redacted[key_string] = "[REDACTED]"
            else:
                redacted[key_string] = redact_sensitive_payload(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive_payload(item) for item in value]
    return value


def sanitize_public_url(value: str, *, allow_path: bool) -> str:
    parsed = urlsplit(str(value).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise InvalidInput("url must be http or https")
    if parsed.username or parsed.password:
        raise InvalidInput("url must not contain credentials")
    if parsed.fragment:
        raise InvalidInput("url must not contain fragments")
    for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered in TOKEN_QUERY_NAMES or "token" in lowered or "secret" in lowered or "password" in lowered:
            raise InvalidInput("url must not contain token-like query parameters")
    path = parsed.path.rstrip("/") if allow_path else ""
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))
