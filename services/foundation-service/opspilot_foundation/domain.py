from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


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
class AuditEvent:
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = ""
    occurred_at: str = ""
