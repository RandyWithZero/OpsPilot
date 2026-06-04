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
    path: str
    web_url: str = ""

    def validate(self) -> None:
        if not self.provider or not self.profile_id or not self.repository_id or not self.path:
            raise InvalidInput("repository bindings require provider, profile_id, repository_id, and path")


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
