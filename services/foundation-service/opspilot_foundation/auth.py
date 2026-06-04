from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .domain import DomainError


class PermissionDenied(DomainError):
    code = "permission_denied"
    status = 403


@dataclass(frozen=True)
class ActorContext:
    actor_id: str
    role: str


ROLE_ADMIN = "Admin"
ROLE_OPERATOR = "Operator"
ROLE_VIEWER = "Viewer"

PERMISSION_READ = "read"
PERMISSION_OPERATE = "operate"
PERMISSION_ADMIN = "admin"

ROLE_PERMISSIONS = {
    ROLE_ADMIN: {PERMISSION_READ, PERMISSION_OPERATE, PERMISSION_ADMIN},
    ROLE_OPERATOR: {PERMISSION_READ, PERMISSION_OPERATE},
    ROLE_VIEWER: {PERMISSION_READ},
}

ARCHIVE_STATUSES = {"archived", "retired", "deleted"}


def actor_from_headers(headers: Mapping[str, str]) -> ActorContext:
    return ActorContext(
        actor_id=str(headers.get("X-Actor-ID", "") or "system"),
        role=normalize_role(headers.get("X-Actor-Role", "")),
    )


def normalize_role(raw_role: str | None) -> str:
    role = str(raw_role or "").strip().lower()
    if not role:
        return ROLE_ADMIN
    aliases = {
        "admin": ROLE_ADMIN,
        "administrator": ROLE_ADMIN,
        "operator": ROLE_OPERATOR,
        "ops": ROLE_OPERATOR,
        "viewer": ROLE_VIEWER,
        "read_only": ROLE_VIEWER,
        "read-only": ROLE_VIEWER,
    }
    return aliases.get(role, "")


def require_permission(actor: ActorContext, permission: str) -> None:
    if permission not in ROLE_PERMISSIONS.get(actor.role, set()):
        raise PermissionDenied("actor role is not allowed to perform this operation")


def permission_for_request(method: str, path: str, body: dict[str, Any] | None = None) -> str:
    method = method.upper()
    body = body or {}
    if method in {"GET", "OPTIONS"}:
        if path in {"/v1/credentials", "/v1/audit-events"}:
            return PERMISSION_ADMIN
        return PERMISSION_READ
    if method == "DELETE":
        return PERMISSION_ADMIN
    if method == "POST":
        if path == "/v1/credentials" or path == "/v1/gitlab/profiles" or path == "/v1/model-providers":
            return PERMISSION_ADMIN
        if path == "/v1/agents" or path == "/v1/skills":
            return PERMISSION_ADMIN
        return PERMISSION_OPERATE
    if method == "PATCH":
        if path.startswith("/v1/credentials/") or path.startswith("/v1/gitlab/profiles/") or path.startswith("/v1/model-providers/"):
            return PERMISSION_ADMIN
        if _is_archive_update(body):
            return PERMISSION_ADMIN
        return PERMISSION_OPERATE
    return PERMISSION_ADMIN


def _is_archive_update(body: dict[str, Any]) -> bool:
    status = str(body.get("status", "")).strip().lower()
    return status in ARCHIVE_STATUSES
