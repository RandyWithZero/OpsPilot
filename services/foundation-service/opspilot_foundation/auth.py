from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from .domain import DomainError


class AuthenticationRequired(DomainError):
    code = "authentication_required"
    status = 401


class PermissionDenied(DomainError):
    code = "permission_denied"
    status = 403


@dataclass(frozen=True)
class ActorContext:
    actor_id: str
    role: str
    subject_type: str = "user"
    session_id: str = ""


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
TOKEN_VERSION = "opspilot.v1"
DEFAULT_ACCESS_TOKEN_TTL_SECONDS = 15 * 60
DEFAULT_REFRESH_TOKEN_TTL_SECONDS = 30 * 24 * 60 * 60


def actor_from_headers(headers: Mapping[str, str]) -> ActorContext:
    return ActorContext(
        actor_id=str(headers.get("X-Actor-ID", "") or "system"),
        role=normalize_role(headers.get("X-Actor-Role", "")),
    )


def dev_headers_enabled() -> bool:
    return os.environ.get("OPSPILOT_AUTH_DEV_HEADERS", "").strip().lower() in {"1", "true", "yes", "on"}


def dev_issuer_enabled() -> bool:
    return os.environ.get("OPSPILOT_AUTH_DEV_ISSUER", "").strip().lower() in {"1", "true", "yes", "on"}


def dev_issuer_password() -> str:
    return os.environ.get("OPSPILOT_AUTH_DEV_PASSWORD", "")


def normalize_role(raw_role: str | None) -> str:
    role = str(raw_role or "").strip().lower()
    if not role:
        return ROLE_VIEWER
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


def token_secret() -> bytes:
    configured = os.environ.get("OPSPILOT_AUTH_TOKEN_SECRET", "")
    if configured:
        return configured.encode("utf-8")
    if dev_issuer_enabled() or dev_headers_enabled():
        return b"opspilot-local-development-token-secret"
    raise RuntimeError("OPSPILOT_AUTH_TOKEN_SECRET is required when development auth is disabled")


def issue_access_token(actor: ActorContext, expires_in_seconds: int | None = None) -> tuple[str, str]:
    ttl = int(expires_in_seconds or os.environ.get("OPSPILOT_AUTH_ACCESS_TTL_SECONDS", DEFAULT_ACCESS_TOKEN_TTL_SECONDS))
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)
    payload = {
        "sub": actor.actor_id,
        "role": actor.role,
        "subject_type": actor.subject_type,
        "session_id": actor.session_id,
        "exp": int(expires_at.timestamp()),
    }
    token_payload = _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _sign(token_payload)
    return f"{TOKEN_VERSION}.{token_payload}.{signature}", expires_at.isoformat()


def actor_from_bearer_token(token: str) -> ActorContext:
    parts = token.strip().split(".")
    if len(parts) != 4 or ".".join(parts[:2]) != TOKEN_VERSION:
        raise AuthenticationRequired("access token is invalid")
    token_payload, signature = parts[2], parts[3]
    if not hmac.compare_digest(_sign(token_payload), signature):
        raise AuthenticationRequired("access token is invalid")
    try:
        payload = json.loads(_b64url_decode(token_payload).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise AuthenticationRequired("access token is invalid") from exc
    if int(payload.get("exp", 0)) <= int(datetime.now(timezone.utc).timestamp()):
        raise AuthenticationRequired("access token is expired")
    role = normalize_role(payload.get("role"))
    if not role:
        raise AuthenticationRequired("access token role is invalid")
    actor_id = str(payload.get("sub", "")).strip()
    if not actor_id:
        raise AuthenticationRequired("access token subject is invalid")
    return ActorContext(
        actor_id=actor_id,
        role=role,
        subject_type=str(payload.get("subject_type", "user") or "user"),
        session_id=str(payload.get("session_id", "") or ""),
    )


def bearer_token_from_headers(headers: Mapping[str, str]) -> str:
    authorization = str(headers.get("Authorization", "") or "").strip()
    if not authorization:
        raise AuthenticationRequired("authorization bearer token is required")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthenticationRequired("authorization bearer token is required")
    return token.strip()


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_expires_at() -> str:
    ttl = int(os.environ.get("OPSPILOT_AUTH_REFRESH_TTL_SECONDS", DEFAULT_REFRESH_TOKEN_TTL_SECONDS))
    return (datetime.now(timezone.utc) + timedelta(seconds=ttl)).isoformat()


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
        if path == "/v1/auth/logout":
            return PERMISSION_READ
        if path == "/v1/credentials" or path == "/v1/gitlab/profiles" or path == "/v1/model-providers" or path == "/v1/users" or path == "/v1/service-identities":
            return PERMISSION_ADMIN
        if path == "/v1/agents" or path == "/v1/skills":
            return PERMISSION_ADMIN
        if path.startswith("/v1/service-identities/"):
            return PERMISSION_ADMIN
        return PERMISSION_OPERATE
    if method == "PATCH":
        if (
            path.startswith("/v1/credentials/")
            or path.startswith("/v1/gitlab/profiles/")
            or path.startswith("/v1/model-providers/")
            or path.startswith("/v1/users/")
            or path.startswith("/v1/agents/")
            or path.startswith("/v1/skills/")
        ):
            return PERMISSION_ADMIN
        if _is_archive_update(body):
            return PERMISSION_ADMIN
        return PERMISSION_OPERATE
    return PERMISSION_ADMIN


def _is_archive_update(body: dict[str, Any]) -> bool:
    status = str(body.get("status", "")).strip().lower()
    return status in ARCHIVE_STATUSES


def _sign(token_payload: str) -> str:
    return _b64url(hmac.new(token_secret(), token_payload.encode("ascii"), hashlib.sha256).digest())


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))
