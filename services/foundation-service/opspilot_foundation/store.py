from __future__ import annotations

from dataclasses import asdict
from threading import RLock
from typing import Any, TypeVar

from .domain import Asset, AuditEvent, Conflict, Environment, NotFound, Project, User, now_utc

T = TypeVar("T")


class MemoryStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._ids = 0
        self.users: dict[str, User] = {}
        self.projects: dict[str, Project] = {}
        self.assets: dict[str, Asset] = {}
        self.environments: dict[str, Environment] = {}
        self.audit_events: list[AuditEvent] = []

    def health(self) -> dict[str, str]:
        return {"status": "ok"}

    def create_user(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        user = User(**pick(data, User))
        user.validate()
        with self._lock:
            if any(existing.email.lower() == user.email.lower() for existing in self.users.values()):
                raise Conflict("email already exists")
            user.id = self._id("usr")
            stamp(user)
            self.users[user.id] = user
            self._audit(actor_id, "identity.user.created", "user", user.id, {"email": user.email})
            return asdict(user)

    def list_users(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(user) for user in self.users.values()]

    def create_project(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        project = Project(**pick(data, Project))
        project.validate()
        with self._lock:
            if project.owner_id not in self.users:
                raise NotFound("owner not found")
            if any(existing.key.lower() == project.key.lower() for existing in self.projects.values()):
                raise Conflict("project key already exists")
            project.id = self._id("prj")
            project.member_ids = unique([*project.member_ids, project.owner_id])
            stamp(project)
            self.projects[project.id] = project
            self._audit(actor_id, "project.created", "project", project.id, {"key": project.key})
            return asdict(project)

    def list_projects(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(project) for project in self.projects.values()]

    def link_project_asset(self, actor_id: str, project_id: str, asset_id: str) -> dict[str, Any]:
        with self._lock:
            project = self._project(project_id)
            if asset_id not in self.assets:
                raise NotFound("asset not found")
            project.asset_ids = unique([*project.asset_ids, asset_id])
            project.updated_at = now_utc()
            self._audit(actor_id, "project.asset.linked", "project", project.id, {"asset_id": asset_id})
            return asdict(project)

    def link_project_environment(self, actor_id: str, project_id: str, environment_id: str) -> dict[str, Any]:
        with self._lock:
            project = self._project(project_id)
            environment = self._environment(environment_id)
            if environment.project_id != project.id:
                raise Conflict("environment belongs to another project")
            project.environment_ids = unique([*project.environment_ids, environment_id])
            project.updated_at = now_utc()
            self._audit(actor_id, "project.environment.linked", "project", project.id, {"environment_id": environment_id})
            return asdict(project)

    def create_asset(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        asset = Asset(**pick(data, Asset))
        asset.validate()
        with self._lock:
            if asset.parent_id and asset.parent_id not in self.assets:
                raise NotFound("parent asset not found")
            asset.id = self._id("ast")
            asset.capabilities = unique(asset.capabilities)
            stamp(asset)
            self.assets[asset.id] = asset
            self._audit(actor_id, "asset.created", "asset", asset.id, {"category": asset.category})
            return asdict(asset)

    def list_assets(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(asset) for asset in self.assets.values()]

    def create_environment(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        environment = Environment(**pick(data, Environment))
        environment.validate()
        with self._lock:
            if environment.project_id not in self.projects:
                raise NotFound("project not found")
            if environment.owner_id not in self.users:
                raise NotFound("owner not found")
            for asset_id in environment.asset_ids:
                if asset_id not in self.assets:
                    raise NotFound("asset not found")
            environment.id = self._id("env")
            environment.member_ids = unique([*environment.member_ids, environment.owner_id])
            environment.asset_ids = unique(environment.asset_ids)
            stamp(environment)
            self.environments[environment.id] = environment
            project = self.projects[environment.project_id]
            project.environment_ids = unique([*project.environment_ids, environment.id])
            project.updated_at = environment.updated_at
            self._audit(actor_id, "environment.created", "environment", environment.id, {"project_id": environment.project_id, "type": environment.type})
            return asdict(environment)

    def list_environments(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(environment) for environment in self.environments.values()]

    def list_audit_events(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(event) for event in reversed(self.audit_events)]

    def _project(self, project_id: str) -> Project:
        if project_id not in self.projects:
            raise NotFound("project not found")
        return self.projects[project_id]

    def _environment(self, environment_id: str) -> Environment:
        if environment_id not in self.environments:
            raise NotFound("environment not found")
        return self.environments[environment_id]

    def _id(self, prefix: str) -> str:
        self._ids += 1
        return f"{prefix}_{self._ids:06d}"

    def _audit(self, actor_id: str, action: str, resource_type: str, resource_id: str, metadata: dict[str, Any]) -> None:
        event = AuditEvent(
            id=self._id("aud"),
            actor_id=actor_id or "system",
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            occurred_at=now_utc(),
            metadata=metadata,
        )
        self.audit_events.append(event)


def unique(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = str(value).strip()
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def stamp(entity: Any) -> None:
    value = now_utc()
    entity.created_at = value
    entity.updated_at = value


def pick(data: dict[str, Any], model: type[T]) -> dict[str, Any]:
    fields = set(model.__dataclass_fields__.keys())  # type: ignore[attr-defined]
    return {key: value for key, value in data.items() if key in fields}
