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
    storage_key: str = ""
    status: str = "pending_upload"
    id: str = ""
    created_at: str = ""
    updated_at: str = ""

    def validate(self) -> None:
        if not self.filename or not self.content_type or int(self.size_bytes) < 0:
            raise InvalidInput("files require filename, content_type, and non-negative size_bytes")


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
    path: str = ""
    web_url: str = ""

    def validate(self) -> None:
        if not self.provider or not self.profile_id or not self.repository_id:
            raise InvalidInput("repository bindings require provider, profile_id, and repository_id")


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
class AuditEvent:
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = ""
    occurred_at: str = ""


TOKEN_QUERY_NAMES = {"access_token", "auth_token", "api_token", "private_token", "token", "key", "secret", "password"}


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
