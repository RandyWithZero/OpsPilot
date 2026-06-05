from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import base64
import json
import xml.etree.ElementTree as ET
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any, TypeVar

from .auth import ActorContext, AuthenticationRequired, PermissionDenied, hash_token, issue_access_token, new_refresh_token, normalize_role, refresh_expires_at
from .domain import (
    Agent,
    Asset,
    AuthSession,
    AuditEvent,
    Conflict,
    CredentialReference,
    Environment,
    FileObject,
    GitLabProfile,
    InvalidInput,
    ModelProvider,
    NotFound,
    Project,
    QualityGate,
    Report,
    RepositoryBinding,
    ServiceIdentity,
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
    WorkflowRuntimeTask,
    WorkflowStepRun,
    WorkflowVersion,
    now_utc,
    redact_sensitive_payload,
    sanitize_public_url,
)
from .storage import ObjectStorage, storage_from_env
from .vcs import GitLabAPIClient, GitLabClient, LocalGitLabClient

T = TypeVar("T")
MAX_FILE_UPLOAD_BYTES = int(os.environ.get("OPSPILOT_MAX_FILE_UPLOAD_BYTES", str(5 * 1024 * 1024)))


class MemoryStore:
    def __init__(self, storage: ObjectStorage | None = None, gitlab_client: GitLabClient | None = None) -> None:
        self._lock = RLock()
        self._ids = 0
        self.users: dict[str, User] = {}
        self.auth_sessions: dict[str, AuthSession] = {}
        self.service_identities: dict[str, ServiceIdentity] = {}
        self.projects: dict[str, Project] = {}
        self.assets: dict[str, Asset] = {}
        self.environments: dict[str, Environment] = {}
        self.files: dict[str, FileObject] = {}
        self.upload_sessions: dict[str, UploadSession] = {}
        self.credentials: dict[str, CredentialReference] = {}
        self.gitlab_profiles: dict[str, GitLabProfile] = {}
        self.vcs_operations: dict[str, VCSOperation] = {}
        self.vcs_webhook_events: dict[str, VCSWebhookEvent] = {}
        self.agents: dict[str, Agent] = {}
        self.skills: dict[str, Skill] = {}
        self.model_providers: dict[str, ModelProvider] = {}
        self.workflows: dict[str, WorkflowDefinition] = {}
        self.workflow_versions: dict[str, WorkflowVersion] = {}
        self.workflow_runs: dict[str, WorkflowRun] = {}
        self.workflow_step_runs: dict[str, WorkflowStepRun] = {}
        self.workflow_runtime_tasks: dict[str, WorkflowRuntimeTask] = {}
        self.test_cases: dict[str, TestCase] = {}
        self.test_suites: dict[str, TestSuite] = {}
        self.test_runs: dict[str, TestRun] = {}
        self.reports: dict[str, Report] = {}
        self.quality_gates: dict[str, QualityGate] = {}
        self.secret_store = LocalSecretStore()
        self.storage = storage or storage_from_env()
        self.storage.ensure_bucket()
        self.gitlab_client = gitlab_client or (GitLabAPIClient() if os.environ.get("OPSPILOT_GITLAB_LIVE") == "1" else LocalGitLabClient())
        self.audit_events: list[AuditEvent] = []

    def health(self) -> dict[str, str]:
        return {"status": "ok"}

    def issue_dev_session(self, data: dict[str, Any]) -> dict[str, Any]:
        role = normalize_role(data.get("role"))
        if not role:
            raise InvalidInput("role is invalid")
        actor_id = str(data.get("actor_id", "") or "").strip()
        email = str(data.get("email", "") or "").strip().lower()
        with self._lock:
            user = self.users.get(actor_id) if actor_id else None
            if user is None and email:
                user = next((candidate for candidate in self.users.values() if candidate.email.lower() == email), None)
            if user is None:
                if not actor_id:
                    actor_id = self._id("usr")
                user = User(email=email or f"{actor_id}@local.opspilot", name=str(data.get("name", "") or actor_id), roles=[{"scope": "platform", "name": role}], id=actor_id)
                stamp(user)
                self.users[user.id] = user
                self._audit(user.id, "identity.user.created", "user", user.id, {"email": user.email, "source": "dev_auth_issuer"})
            elif not any(normalize_role(existing.get("name")) == role for existing in user.roles):
                user.roles = [{"scope": "platform", "name": role}]
                user.updated_at = now_utc()
            return self._create_session(user.id, role)

    def refresh_session(self, data: dict[str, Any]) -> dict[str, Any]:
        refresh_token_value = str(data.get("refresh_token", "") or "")
        if not refresh_token_value:
            raise AuthenticationRequired("refresh token is required")
        token_hash = hash_token(refresh_token_value)
        with self._lock:
            session = next((candidate for candidate in self.auth_sessions.values() if candidate.refresh_token_hash == token_hash), None)
            if session is None or session.status != "active" or _is_past(session.expires_at):
                raise AuthenticationRequired("refresh token is invalid")
            user_role = self._active_user_role(session.user_id)
            session.expires_at = refresh_expires_at()
            session.updated_at = now_utc()
            session.role = user_role
            refresh_token = new_refresh_token()
            session.refresh_token_hash = hash_token(refresh_token)
            access_token, access_expires_at = issue_access_token(ActorContext(actor_id=session.user_id, role=user_role, session_id=session.id))
            self._audit(session.user_id, "auth.session.refreshed", "auth_session", session.id, {"subject_type": "user"})
            return {"access_token": access_token, "access_token_expires_at": access_expires_at, "refresh_token": refresh_token, "refresh_token_expires_at": session.expires_at, "token_type": "Bearer"}

    def logout_session(self, actor_id: str, data: dict[str, Any]) -> dict[str, str]:
        session_id = str(data.get("session_id", "") or "").strip()
        refresh_token = str(data.get("refresh_token", "") or "")
        refresh_hash = hash_token(refresh_token) if refresh_token else ""
        with self._lock:
            for session in self.auth_sessions.values():
                if (session_id and session.id == session_id) or (refresh_hash and session.refresh_token_hash == refresh_hash):
                    session.status = "revoked"
                    session.revoked_at = now_utc()
                    session.updated_at = session.revoked_at
                    self._audit(actor_id, "auth.session.revoked", "auth_session", session.id, {"subject_type": "user"})
                    return {"status": "revoked"}
        return {"status": "not_found"}

    def create_service_identity(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        role = normalize_role(data.get("role"))
        if not role:
            raise InvalidInput("role is invalid")
        service_token = new_refresh_token()
        identity = ServiceIdentity(
            name=str(data.get("name", "") or "").strip(),
            role=role,
            token_hash=hash_token(service_token),
            project_ids=self._normalize_service_identity_project_ids(data),
        )
        identity.validate()
        with self._lock:
            for project_id in identity.project_ids:
                self._project(project_id)
            if any(existing.name.lower() == identity.name.lower() for existing in self.service_identities.values()):
                raise Conflict("service identity name already exists")
            identity.id = self._id("svc")
            stamp(identity)
            self.service_identities[identity.id] = identity
            access_token, access_expires_at = issue_access_token(ActorContext(actor_id=identity.id, role=identity.role, subject_type="service", session_id=identity.id), int(data.get("access_token_ttl_seconds", 3600)))
            self._audit(actor_id, "auth.service_identity.created", "service_identity", identity.id, {"name": identity.name, "role": identity.role})
            return {**self._public_service_identity(identity), "service_token": service_token, "access_token": access_token, "access_token_expires_at": access_expires_at, "token_type": "Bearer"}

    def list_service_identities(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._public_service_identity(identity) for identity in self.service_identities.values()]

    def issue_service_identity_token(self, actor_id: str, service_identity_id: str, data: dict[str, Any]) -> dict[str, Any]:
        service_token = str(data.get("service_token", "") or "")
        if not service_token:
            raise AuthenticationRequired("service identity token is required")
        service_token_hash = hash_token(service_token)
        with self._lock:
            identity = self.service_identities.get(service_identity_id)
            if identity is None:
                raise NotFound("service identity not found")
            if identity.status != "active" or identity.token_hash != service_token_hash:
                raise AuthenticationRequired("service identity token is invalid")
            access_token, access_expires_at = issue_access_token(ActorContext(actor_id=identity.id, role=identity.role, subject_type="service", session_id=identity.id), int(data.get("access_token_ttl_seconds", 3600)))
            self._audit(actor_id, "auth.service_identity.token_issued", "service_identity", identity.id, {"subject_type": "service"})
            return {"access_token": access_token, "access_token_expires_at": access_expires_at, "token_type": "Bearer"}

    def revoke_service_identity(self, actor_id: str, service_identity_id: str) -> dict[str, str]:
        with self._lock:
            identity = self.service_identities.get(service_identity_id)
            if identity is None:
                raise NotFound("service identity not found")
            identity.status = "revoked"
            identity.revoked_at = now_utc()
            identity.updated_at = identity.revoked_at
            self._audit(actor_id, "auth.service_identity.revoked", "service_identity", identity.id, {"name": identity.name})
            return {"status": "revoked"}

    def validate_actor_session(self, actor: ActorContext) -> ActorContext:
        with self._lock:
            if actor.subject_type == "service":
                identity = self.service_identities.get(actor.actor_id)
                if identity is None or identity.status != "active":
                    raise AuthenticationRequired("service identity is not active")
                return ActorContext(actor_id=identity.id, role=identity.role, subject_type="service", session_id=identity.id)
            session = self.auth_sessions.get(actor.session_id)
            if session is None or session.status != "active" or _is_past(session.expires_at):
                raise AuthenticationRequired("session is not active")
            if session.user_id != actor.actor_id:
                raise AuthenticationRequired("session subject mismatch")
            user_role = self._active_user_role(session.user_id)
            return ActorContext(actor_id=session.user_id, role=user_role, subject_type="user", session_id=session.id)

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

    def _create_session(self, user_id: str, role: str) -> dict[str, Any]:
        refresh_token = new_refresh_token()
        session = AuthSession(user_id=user_id, role=role, refresh_token_hash=hash_token(refresh_token), expires_at=refresh_expires_at())
        session.id = self._id("ses")
        stamp(session)
        self.auth_sessions[session.id] = session
        access_token, access_expires_at = issue_access_token(ActorContext(actor_id=user_id, role=role, session_id=session.id))
        self._audit(user_id, "auth.session.created", "auth_session", session.id, {"subject_type": "user", "role": role})
        return {"access_token": access_token, "access_token_expires_at": access_expires_at, "refresh_token": refresh_token, "refresh_token_expires_at": session.expires_at, "session_id": session.id, "token_type": "Bearer"}

    def _public_service_identity(self, identity: ServiceIdentity) -> dict[str, Any]:
        data = asdict(identity)
        data.pop("token_hash", None)
        return data

    def _normalize_service_identity_project_ids(self, data: dict[str, Any]) -> list[str]:
        raw_project_ids = data.get("project_ids", [])
        if "project_id" in data and data.get("project_id"):
            raw_project_ids = [*raw_project_ids, data.get("project_id")] if isinstance(raw_project_ids, list) else [data.get("project_id")]
        if raw_project_ids in (None, ""):
            return []
        if not isinstance(raw_project_ids, list):
            raise InvalidInput("service identity project_ids must be an array")
        project_ids: list[str] = []
        for project_id in raw_project_ids:
            value = str(project_id or "").strip()
            if not value:
                raise InvalidInput("service identity project_ids cannot contain empty values")
            project_ids.append(value)
        return unique(project_ids)

    def _active_user_role(self, user_id: str) -> str:
        user = self.users.get(user_id)
        if user is None or user.status != "active":
            raise AuthenticationRequired("session user is not active")
        role = highest_role(user.roles)
        if not role:
            raise AuthenticationRequired("session user has no active role")
        return role

    def list_users(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(user) for user in self.users.values()]

    def update_user(self, actor_id: str, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if user_id not in self.users:
                raise NotFound("user not found")
            user = self.users[user_id]
            if "email" in data and any(existing.id != user_id and existing.email.lower() == str(data["email"]).lower() for existing in self.users.values()):
                raise Conflict("email already exists")
            for key in ("email", "name", "roles", "status"):
                if key in data:
                    setattr(user, key, data[key])
            user.validate()
            user.updated_at = now_utc()
            self._audit(actor_id, "identity.user.updated", "user", user.id, {"status": user.status})
            return asdict(user)

    def delete_user(self, actor_id: str, user_id: str) -> dict[str, str]:
        with self._lock:
            user = self.users.pop(user_id, None)
            if user is None:
                raise NotFound("user not found")
            for session in self.auth_sessions.values():
                if session.user_id == user_id:
                    session.status = "revoked"
                    session.revoked_at = now_utc()
                    session.updated_at = session.revoked_at
            for project in self.projects.values():
                project.member_ids = [member_id for member_id in project.member_ids if member_id != user_id]
                if project.owner_id == user_id:
                    project.owner_id = ""
                project.updated_at = now_utc()
            for environment in self.environments.values():
                environment.member_ids = [member_id for member_id in environment.member_ids if member_id != user_id]
                if environment.owner_id == user_id:
                    environment.owner_id = ""
                environment.updated_at = now_utc()
            self._audit(actor_id, "identity.user.deleted", "user", user_id, {"email": user.email})
            return {"status": "deleted"}

    def create_project(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        project = Project(**pick(data, Project))
        project.validate()
        with self._lock:
            if project.owner_id not in self.users:
                raise NotFound("owner not found")
            for member_id in project.member_ids:
                if member_id not in self.users:
                    raise NotFound("member not found")
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

    def update_project(self, actor_id: str, project_id: str, data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            project = self._project(project_id)
            if "owner_id" in data and data["owner_id"] and data["owner_id"] not in self.users:
                raise NotFound("owner not found")
            for member_id in data.get("member_ids", []):
                if member_id not in self.users:
                    raise NotFound("member not found")
            if "key" in data and any(existing.id != project_id and existing.key.lower() == str(data["key"]).lower() for existing in self.projects.values()):
                raise Conflict("project key already exists")
            for key in ("key", "name", "owner_id", "description", "member_ids", "status"):
                if key in data:
                    setattr(project, key, data[key])
            project.member_ids = unique([*project.member_ids, project.owner_id])
            project.validate()
            project.updated_at = now_utc()
            self._audit(actor_id, "project.updated", "project", project.id, {"status": project.status})
            return asdict(project)

    def delete_project(self, actor_id: str, project_id: str) -> dict[str, str]:
        with self._lock:
            project = self.projects.pop(project_id, None)
            if project is None:
                raise NotFound("project not found")
            for environment_id, environment in list(self.environments.items()):
                if environment.project_id == project_id:
                    self.environments.pop(environment_id, None)
            for workflow_id, workflow in list(self.workflows.items()):
                if workflow.project_id == project_id:
                    self._delete_workflow_cascade(workflow_id)
            for run_id, run in list(self.test_runs.items()):
                if run.project_id == project_id:
                    self.test_runs.pop(run_id, None)
            for suite_id, suite in list(self.test_suites.items()):
                if suite.project_id == project_id:
                    self.test_suites.pop(suite_id, None)
            for case_id, test_case in list(self.test_cases.items()):
                if test_case.project_id == project_id:
                    self.test_cases.pop(case_id, None)
            for report_id, report in list(self.reports.items()):
                if report.project_id == project_id:
                    self.reports.pop(report_id, None)
            for gate_id, gate in list(self.quality_gates.items()):
                if gate.project_id == project_id:
                    self.quality_gates.pop(gate_id, None)
            self._audit(actor_id, "project.deleted", "project", project_id, {"key": project.key})
            return {"status": "deleted"}

    def link_project_asset(self, actor_id: str, project_id: str, asset_id: str) -> dict[str, Any]:
        with self._lock:
            project = self._project(project_id)
            if asset_id not in self.assets:
                raise NotFound("asset not found")
            project.asset_ids = unique([*project.asset_ids, asset_id])
            project.updated_at = now_utc()
            self._audit(actor_id, "project.asset.linked", "project", project.id, {"asset_id": asset_id})
            return asdict(project)

    def unlink_project_asset(self, actor_id: str, project_id: str, asset_id: str) -> dict[str, Any]:
        with self._lock:
            project = self._project(project_id)
            project.asset_ids = [existing_id for existing_id in project.asset_ids if existing_id != asset_id]
            project.updated_at = now_utc()
            self._audit(actor_id, "project.asset.unlinked", "project", project.id, {"asset_id": asset_id})
            return asdict(project)

    def link_environment_asset(self, actor_id: str, environment_id: str, asset_id: str) -> dict[str, Any]:
        with self._lock:
            environment = self._environment(environment_id)
            project = self._project(environment.project_id)
            self._validate_environment_asset(project, asset_id)
            environment.asset_ids = unique([*environment.asset_ids, asset_id])
            environment.updated_at = now_utc()
            self._audit(actor_id, "environment.asset.linked", "environment", environment.id, {"asset_id": asset_id})
            return asdict(environment)

    def unlink_environment_asset(self, actor_id: str, environment_id: str, asset_id: str) -> dict[str, Any]:
        with self._lock:
            environment = self._environment(environment_id)
            environment.asset_ids = [existing_id for existing_id in environment.asset_ids if existing_id != asset_id]
            environment.updated_at = now_utc()
            self._audit(actor_id, "environment.asset.unlinked", "environment", environment.id, {"asset_id": asset_id})
            return asdict(environment)

    def link_environment_member(self, actor_id: str, environment_id: str, user_id: str) -> dict[str, Any]:
        with self._lock:
            environment = self._environment(environment_id)
            project = self._project(environment.project_id)
            self._validate_environment_member(project, user_id)
            environment.member_ids = unique([*environment.member_ids, user_id])
            environment.updated_at = now_utc()
            self._audit(actor_id, "environment.member.linked", "environment", environment.id, {"user_id": user_id})
            return asdict(environment)

    def unlink_environment_member(self, actor_id: str, environment_id: str, user_id: str) -> dict[str, Any]:
        with self._lock:
            environment = self._environment(environment_id)
            if user_id == environment.owner_id:
                raise Conflict("environment owner cannot be unlinked")
            environment.member_ids = [existing_id for existing_id in environment.member_ids if existing_id != user_id]
            environment.updated_at = now_utc()
            self._audit(actor_id, "environment.member.unlinked", "environment", environment.id, {"user_id": user_id})
            return asdict(environment)

    def link_environment_file(self, actor_id: str, environment_id: str, file_id: str) -> dict[str, Any]:
        with self._lock:
            environment = self._environment(environment_id)
            project = self._project(environment.project_id)
            self._require_project_actor(actor_id, project)
            self._claim_or_validate_environment_file(actor_id, environment, file_id)
            environment.file_ids = unique([*environment.file_ids, file_id])
            environment.updated_at = now_utc()
            self._audit(actor_id, "environment.file.linked", "environment", environment.id, {"file_id": file_id})
            return asdict(environment)

    def unlink_environment_file(self, actor_id: str, environment_id: str, file_id: str) -> dict[str, Any]:
        with self._lock:
            environment = self._environment(environment_id)
            environment.file_ids = [existing_id for existing_id in environment.file_ids if existing_id != file_id]
            environment.updated_at = now_utc()
            self._audit(actor_id, "environment.file.unlinked", "environment", environment.id, {"file_id": file_id})
            return asdict(environment)

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

    def unlink_project_environment(self, actor_id: str, project_id: str, environment_id: str) -> dict[str, Any]:
        with self._lock:
            project = self._project(project_id)
            project.environment_ids = [existing_id for existing_id in project.environment_ids if existing_id != environment_id]
            project.updated_at = now_utc()
            self._audit(actor_id, "project.environment.unlinked", "project", project.id, {"environment_id": environment_id})
            return asdict(project)

    def link_project_repository(self, actor_id: str, project_id: str, data: dict[str, Any]) -> dict[str, Any]:
        binding = RepositoryBinding(**pick(data, RepositoryBinding))
        binding.validate()
        with self._lock:
            project = self._project(project_id)
            if binding.provider != "gitlab":
                raise InvalidInput("only gitlab repository bindings are supported")
            profile = self._gitlab_profile(binding.profile_id)
            repositories = {repo["id"]: repo for repo in self.list_gitlab_repositories(binding.profile_id)}
            if binding.repository_id not in repositories:
                raise NotFound("repository not found for profile")
            serialized = asdict(binding)
            project.repository_bindings = [
                existing
                for existing in project.repository_bindings
                if not (existing["provider"] == serialized["provider"] and existing["profile_id"] == serialized["profile_id"] and existing["repository_id"] == serialized["repository_id"])
            ]
            project.repository_bindings.append(serialized)
            project.updated_at = now_utc()
            self._audit(actor_id, "project.repository.linked", "project", project.id, {"provider": "gitlab", "profile_id": profile.id, "repository_id": binding.repository_id})
            return asdict(project)

    def unlink_project_repository(self, actor_id: str, project_id: str, profile_id: str, repository_id: str) -> dict[str, Any]:
        with self._lock:
            project = self._project(project_id)
            project.repository_bindings = [
                existing
                for existing in project.repository_bindings
                if not (existing["provider"] == "gitlab" and existing["profile_id"] == profile_id and existing["repository_id"] == repository_id)
            ]
            project.updated_at = now_utc()
            self._audit(actor_id, "project.repository.unlinked", "project", project.id, {"provider": "gitlab", "profile_id": profile_id, "repository_id": repository_id})
            return asdict(project)

    def create_asset(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        asset = Asset(**pick(data, Asset))
        asset.validate()
        with self._lock:
            if asset.parent_id and asset.parent_id not in self.assets:
                raise NotFound("parent asset not found")
            asset.id = self._id("ast")
            self._validate_asset_files(asset)
            asset.capabilities = unique(asset.capabilities)
            asset.tags = unique(asset.tags)
            asset.file_ids = unique(asset.file_ids)
            stamp(asset)
            self.assets[asset.id] = asset
            self._audit(actor_id, "asset.created", "asset", asset.id, {"category": asset.category})
            return asdict(asset)

    def list_assets(self, filters: dict[str, str] | None = None) -> list[dict[str, Any]]:
        filters = filters or {}
        with self._lock:
            return [asdict(asset) for asset in self.assets.values() if self._matches_asset_filters(asset, filters)]

    def update_asset(self, actor_id: str, asset_id: str, data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if asset_id not in self.assets:
                raise NotFound("asset not found")
            asset = self.assets[asset_id]
            if "parent_id" in data and data["parent_id"]:
                if data["parent_id"] == asset_id:
                    raise Conflict("asset cannot be its own parent")
                if data["parent_id"] not in self.assets:
                    raise NotFound("parent asset not found")
                self._validate_asset_parent(asset_id, str(data["parent_id"]))
            for key in ("category", "name", "status", "owner_id", "location", "parent_id", "capabilities", "tags", "file_ids", "properties"):
                if key in data:
                    setattr(asset, key, data[key])
            asset.capabilities = unique(asset.capabilities)
            asset.tags = unique(asset.tags)
            asset.file_ids = unique(asset.file_ids)
            self._validate_asset_files(asset)
            asset.validate()
            asset.updated_at = now_utc()
            if asset.status in {"retired", "archived", "deleted"}:
                self._cleanup_asset_references(asset.id)
            self._audit(actor_id, "asset.updated", "asset", asset.id, {"status": asset.status})
            return asdict(asset)

    def delete_asset(self, actor_id: str, asset_id: str) -> dict[str, str]:
        with self._lock:
            asset = self.assets.pop(asset_id, None)
            if asset is None:
                raise NotFound("asset not found")
            self._cleanup_asset_references(asset_id)
            for child in self.assets.values():
                if child.parent_id == asset_id:
                    child.parent_id = ""
                    child.updated_at = now_utc()
            self._audit(actor_id, "asset.deleted", "asset", asset_id, {"name": asset.name})
            return {"status": "deleted"}

    def create_environment(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        environment = Environment(**pick(data, Environment))
        environment.validate()
        with self._lock:
            if environment.project_id not in self.projects:
                raise NotFound("project not found")
            project = self._project(environment.project_id)
            self._validate_environment_member(project, environment.owner_id)
            for member_id in environment.member_ids:
                self._validate_environment_member(project, member_id)
            for asset_id in environment.asset_ids:
                self._validate_environment_asset(project, asset_id)
            environment.id = self._id("env")
            self._validate_environment_files(actor_id, environment)
            environment.member_ids = unique([*environment.member_ids, environment.owner_id])
            environment.asset_ids = unique(environment.asset_ids)
            environment.file_ids = unique(environment.file_ids)
            stamp(environment)
            self.environments[environment.id] = environment
            project.environment_ids = unique([*project.environment_ids, environment.id])
            project.updated_at = environment.updated_at
            self._audit(actor_id, "environment.created", "environment", environment.id, {"project_id": environment.project_id, "type": environment.type})
            return asdict(environment)

    def list_environments(self, filters: dict[str, str] | None = None) -> list[dict[str, Any]]:
        filters = filters or {}
        with self._lock:
            return [asdict(environment) for environment in self.environments.values() if self._matches_environment_filters(environment, filters)]

    def update_environment(self, actor_id: str, environment_id: str, data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            environment = self._environment(environment_id)
            if "project_id" in data and data["project_id"] not in self.projects:
                raise NotFound("project not found")
            old_project_id = environment.project_id
            for key in ("project_id", "name", "type", "status", "owner_id", "member_ids", "asset_ids", "endpoints", "file_ids"):
                if key in data:
                    setattr(environment, key, data[key])
            project = self._project(environment.project_id)
            self._validate_environment_member(project, environment.owner_id)
            for member_id in environment.member_ids:
                self._validate_environment_member(project, member_id)
            for asset_id in environment.asset_ids:
                self._validate_environment_asset(project, asset_id)
            if "file_ids" in data:
                self._validate_environment_files(actor_id, environment)
            environment.member_ids = unique([*environment.member_ids, environment.owner_id])
            environment.asset_ids = unique(environment.asset_ids)
            environment.file_ids = unique(environment.file_ids)
            environment.validate()
            environment.updated_at = now_utc()
            if old_project_id != environment.project_id and old_project_id in self.projects:
                self.projects[old_project_id].environment_ids = [existing_id for existing_id in self.projects[old_project_id].environment_ids if existing_id != environment_id]
            self.projects[environment.project_id].environment_ids = unique([*self.projects[environment.project_id].environment_ids, environment.id])
            self.projects[environment.project_id].updated_at = environment.updated_at
            self._audit(actor_id, "environment.updated", "environment", environment.id, {"status": environment.status})
            return asdict(environment)

    def delete_environment(self, actor_id: str, environment_id: str) -> dict[str, str]:
        with self._lock:
            environment = self.environments.pop(environment_id, None)
            if environment is None:
                raise NotFound("environment not found")
            if environment.project_id in self.projects:
                project = self.projects[environment.project_id]
                project.environment_ids = [existing_id for existing_id in project.environment_ids if existing_id != environment_id]
                project.updated_at = now_utc()
            self._audit(actor_id, "environment.deleted", "environment", environment_id, {"name": environment.name})
            return {"status": "deleted"}

    def create_file_object(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        file_object = FileObject(**pick(data, FileObject))
        file_object.validate()
        with self._lock:
            file_object.id = self._id("fil")
            file_object.storage_key = self._new_storage_key()
            stamp(file_object)
            self.files[file_object.id] = file_object
            self._audit(actor_id, "file.created", "file", file_object.id, self._file_audit_metadata(file_object))
            return self._public_file(file_object)

    def upload_file_object(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        content = self._decode_file_content(data)
        payload = {**data, "size_bytes": len(content)}
        file_object = FileObject(**pick(payload, FileObject))
        file_object.status = "available"
        file_object.checksum = f"sha256:{hashlib.sha256(content).hexdigest()}"
        file_object.validate()
        with self._lock:
            file_object.id = self._id("fil")
            file_object.storage_key = self._new_storage_key()
            stamp(file_object)
            self.storage.put(file_object.storage_key, content)
            self.files[file_object.id] = file_object
            self._audit(actor_id, "file.uploaded", "file", file_object.id, self._file_audit_metadata(file_object))
            return self._public_file(file_object)

    def list_file_objects(self, filters: dict[str, str] | None = None) -> list[dict[str, Any]]:
        filters = filters or {}
        with self._lock:
            return [self._public_file(file_object) for file_object in self.files.values() if self._matches_file_filters(file_object, filters)]

    def download_file_object(self, actor_id: str, file_id: str, filters: dict[str, str] | None = None) -> dict[str, Any]:
        with self._lock:
            file_object = self._file(file_id)
            if file_object.status != "available":
                raise NotFound("file is not available")
            if not self._matches_file_filters(file_object, filters or {}):
                raise NotFound("file not found")
            content = self.storage.get(file_object.storage_key)
            self._audit(actor_id, "file.downloaded", "file", file_object.id, self._file_audit_metadata(file_object))
            return {
                "file": self._public_file(file_object),
                "content_base64": base64.b64encode(content).decode("ascii"),
            }

    def delete_file_object(self, actor_id: str, file_id: str, filters: dict[str, str] | None = None) -> dict[str, str]:
        with self._lock:
            file_object = self._file(file_id)
            if not self._matches_file_filters(file_object, filters or {}):
                raise NotFound("file not found")
            if file_object.status != "deleted":
                self.storage.delete(file_object.storage_key)
                file_object.status = "deleted"
                file_object.deleted_at = now_utc()
                file_object.deleted_by = actor_id or "system"
                file_object.updated_at = file_object.deleted_at
                self._cleanup_file_references(file_object.id)
                self._audit(actor_id, "file.deleted", "file", file_object.id, self._file_audit_metadata(file_object))
            return {"status": "deleted"}

    def create_upload_grant(self, actor_id: str, file_id: str, filters: dict[str, str] | None = None) -> dict[str, Any]:
        with self._lock:
            file_object = self._file(file_id)
            if not self._matches_file_filters(file_object, filters or {}):
                raise NotFound("file not found")
            capability_id = self._id("fgr")
            grant = {
                "file_id": file_object.id,
                "method": "PUT",
                "url": self.storage.capability_url("upload", capability_id),
                "expires_in_seconds": 900,
            }
            self._audit(actor_id, "file.upload_grant.created", "file", file_object.id, {"capability_id": capability_id})
            return grant

    def create_upload_session(self, actor_id: str, file_id: str, filters: dict[str, str] | None = None) -> dict[str, Any]:
        with self._lock:
            file_object = self._file(file_id)
            if not self._matches_file_filters(file_object, filters or {}):
                raise NotFound("file not found")
            session = UploadSession(file_id=file_object.id)
            session.id = self._id("upl")
            session.url = self.storage.capability_url("upload", session.id)
            session.validate()
            stamp(session)
            self.upload_sessions[session.id] = session
            self._audit(actor_id, "file.upload_session.created", "file", file_object.id, {"upload_session_id": session.id})
            return asdict(session)

    def complete_upload_session(self, actor_id: str, session_id: str, data: dict[str, Any], filters: dict[str, str] | None = None) -> dict[str, Any]:
        with self._lock:
            session = self._upload_session(session_id)
            if session.status != "open":
                raise Conflict("upload session is not open")
            file_object = self._file(session.file_id)
            if not self._matches_file_filters(file_object, filters or {}):
                raise NotFound("file not found")
            if "checksum" in data:
                file_object.checksum = str(data["checksum"])
            if "size_bytes" in data:
                file_object.size_bytes = int(data["size_bytes"])
            file_object.status = "available"
            file_object.validate()
            file_object.updated_at = now_utc()
            session.status = "completed"
            session.updated_at = file_object.updated_at
            self._audit(actor_id, "file.upload_session.completed", "file", file_object.id, {"upload_session_id": session.id})
            return {"upload_session": asdict(session), "file": self._public_file(file_object)}

    def create_download_grant(self, actor_id: str, file_id: str, filters: dict[str, str] | None = None) -> dict[str, Any]:
        with self._lock:
            file_object = self._file(file_id)
            if not self._matches_file_filters(file_object, filters or {}):
                raise NotFound("file not found")
            capability_id = self._id("fgr")
            grant = {
                "file_id": file_object.id,
                "method": "GET",
                "url": self.storage.capability_url("download", capability_id),
                "expires_in_seconds": 900,
            }
            self._audit(actor_id, "file.download_grant.created", "file", file_object.id, {"capability_id": capability_id})
            return grant

    def create_credential(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        secret = str(data.get("secret", ""))
        if not secret:
            raise InvalidInput("credentials require secret")
        credential = CredentialReference(**pick(data, CredentialReference))
        credential.validate()
        with self._lock:
            credential.id = self._id("cred")
            credential.secret_ref = self.secret_store.put(secret)
            credential.secret_fingerprint = self.secret_store.fingerprint(secret)
            stamp(credential)
            self.credentials[credential.id] = credential
            self._audit(actor_id, "credential.created", "credential", credential.id, {"provider": credential.provider})
            return asdict(credential)

    def list_credentials(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(credential) for credential in self.credentials.values()]

    def update_credential(self, actor_id: str, credential_id: str, data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            credential = self._credential(credential_id)
            if "provider" in data and data["provider"] != credential.provider:
                raise InvalidInput("credential provider is immutable")
            for key in ("name", "status"):
                if key in data:
                    setattr(credential, key, data[key])
            if "secret" in data:
                secret = str(data["secret"])
                if not secret:
                    raise InvalidInput("secret cannot be empty")
                self.secret_store.rotate(credential.secret_ref, secret)
                credential.secret_fingerprint = self.secret_store.fingerprint(secret)
            credential.validate()
            credential.updated_at = now_utc()
            self._audit(actor_id, "credential.updated", "credential", credential.id, {"provider": credential.provider})
            return asdict(credential)

    def delete_credential(self, actor_id: str, credential_id: str) -> dict[str, str]:
        with self._lock:
            credential = self._credential(credential_id)
            if any(profile.credential_ref_id == credential_id for profile in self.gitlab_profiles.values()):
                raise Conflict("credential is used by a gitlab profile")
            if any(provider.credential_ref_id == credential_id for provider in self.model_providers.values()):
                raise Conflict("credential is used by a model provider")
            self.credentials.pop(credential_id, None)
            self.secret_store.delete(credential.secret_ref)
            self._audit(actor_id, "credential.deleted", "credential", credential_id, {"provider": credential.provider})
            return {"status": "deleted"}

    def create_gitlab_profile(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        if data.get("repository_selection"):
            raise InvalidInput("repository selection is read-only; sync repositories through the GitLab adapter")
        profile = GitLabProfile(**pick(data, GitLabProfile))
        profile.validate()
        with self._lock:
            credential = self._credential(profile.credential_ref_id)
            if credential.provider != "gitlab":
                raise InvalidInput("gitlab profiles require a gitlab credential")
            if any(existing.name.lower() == profile.name.lower() for existing in self.gitlab_profiles.values()):
                raise Conflict("gitlab profile name already exists")
            profile.id = self._id("glp")
            profile.base_url = sanitize_public_url(profile.base_url, allow_path=False)
            profile.repository_selection = []
            webhook_secret = str(data.get("webhook_secret", "")).strip()
            if webhook_secret:
                profile.webhook_secret_ref = self.secret_store.put(webhook_secret)
            stamp(profile)
            self.gitlab_profiles[profile.id] = profile
            self._audit(actor_id, "gitlab.profile.created", "gitlab_profile", profile.id, {"base_url": profile.base_url, "credential_ref_id": profile.credential_ref_id})
            return asdict(profile)

    def list_gitlab_profiles(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(profile) for profile in self.gitlab_profiles.values()]

    def update_gitlab_profile(self, actor_id: str, profile_id: str, data: dict[str, Any]) -> dict[str, Any]:
        if data.get("repository_selection"):
            raise InvalidInput("repository selection is read-only; sync repositories through the GitLab adapter")
        with self._lock:
            profile = self._gitlab_profile(profile_id)
            if "credential_ref_id" in data:
                credential = self._credential(str(data["credential_ref_id"]))
                if credential.provider != "gitlab":
                    raise InvalidInput("gitlab profiles require a gitlab credential")
            if "name" in data and any(existing.id != profile_id and existing.name.lower() == str(data["name"]).lower() for existing in self.gitlab_profiles.values()):
                raise Conflict("gitlab profile name already exists")
            for key in ("name", "base_url", "credential_ref_id", "status"):
                if key in data:
                    setattr(profile, key, data[key])
            profile.validate()
            profile.base_url = sanitize_public_url(profile.base_url, allow_path=False)
            webhook_secret = str(data.get("webhook_secret", "")).strip()
            if webhook_secret:
                if profile.webhook_secret_ref:
                    self.secret_store.rotate(profile.webhook_secret_ref, webhook_secret)
                else:
                    profile.webhook_secret_ref = self.secret_store.put(webhook_secret)
            profile.updated_at = now_utc()
            self._audit(actor_id, "gitlab.profile.updated", "gitlab_profile", profile.id, {"status": profile.status})
            return asdict(profile)

    def delete_gitlab_profile(self, actor_id: str, profile_id: str) -> dict[str, str]:
        with self._lock:
            profile = self.gitlab_profiles.pop(profile_id, None)
            if profile is None:
                raise NotFound("gitlab profile not found")
            for project in self.projects.values():
                project.repository_bindings = [binding for binding in project.repository_bindings if binding["profile_id"] != profile_id]
                project.updated_at = now_utc()
            if profile.webhook_secret_ref:
                self.secret_store.delete(profile.webhook_secret_ref)
            self._audit(actor_id, "gitlab.profile.deleted", "gitlab_profile", profile_id, {"name": profile.name})
            return {"status": "deleted"}

    def sync_gitlab_repositories(self, actor_id: str, profile_id: str, search: str = "", page: int = 1, per_page: int = 20) -> dict[str, Any]:
        with self._lock:
            profile = self._active_gitlab_profile(profile_id)
            credential = self._active_credential(profile.credential_ref_id)
            repositories = self.gitlab_client.list_projects(profile.base_url, self.secret_store.get(credential.secret_ref), search=search, page=page, per_page=per_page)
            profile.repository_selection = normalize_repositories(repositories, profile.base_url)
            profile.repository_synced_at = now_utc()
            profile.updated_at = profile.repository_synced_at
            self._audit(actor_id, "gitlab.repositories.synced", "gitlab_profile", profile.id, {"repository_count": len(profile.repository_selection)})
            return self.discover_gitlab_repositories(profile_id, search=search, page=page, per_page=per_page)

    def discover_gitlab_repositories(self, profile_id: str, search: str = "", page: int = 1, per_page: int = 20) -> dict[str, Any]:
        repositories = self.list_gitlab_repositories(profile_id)
        needle = search.lower().strip()
        if needle:
            repositories = [repo for repo in repositories if needle in repo["path"].lower() or needle in repo["name"].lower()]
        page = max(int(page), 1)
        per_page = min(max(int(per_page), 1), 100)
        start = (page - 1) * per_page
        items = repositories[start : start + per_page]
        profile = self._gitlab_profile(profile_id)
        return {
            "items": items,
            "page": page,
            "per_page": per_page,
            "total": len(repositories),
            "has_next": start + per_page < len(repositories),
            "last_synced_at": profile.repository_synced_at,
        }

    def list_gitlab_repositories(self, profile_id: str) -> list[dict[str, str]]:
        profile = self._gitlab_profile(profile_id)
        if profile.repository_selection:
            return [dict(repository) for repository in profile.repository_selection]
        return normalize_repositories(
            [
                {"id": "stub-ops-platform", "path": "platform/opspilot", "name": "OpsPilot", "web_url": f"{profile.base_url.rstrip('/')}/platform/opspilot"},
                {"id": "stub-infra", "path": "platform/infra", "name": "Infra", "web_url": f"{profile.base_url.rstrip('/')}/platform/infra"},
            ],
            profile.base_url,
        )

    def list_gitlab_branches(self, actor_id: str, project_id: str, profile_id: str, repository_id: str) -> dict[str, Any]:
        with self._lock:
            self._project_repository_binding(actor_id, project_id, profile_id, repository_id)
            profile = self._active_gitlab_profile(profile_id)
            credential = self._active_credential(profile.credential_ref_id)
            repository = self._gitlab_repository(profile_id, repository_id)
            branches = self.gitlab_client.list_branches(profile.base_url, self.secret_store.get(credential.secret_ref), repository_id)
            self._audit(actor_id, "gitlab.branches.read", "gitlab_repository", repository_id, {"profile_id": profile_id})
            return {"repository": repository, "branches": branches}

    def create_gitlab_branch(self, actor_id: str, profile_id: str, repository_id: str, data: dict[str, Any]) -> dict[str, Any]:
        branch = str(data.get("branch", "")).strip()
        ref = str(data.get("ref", "")).strip()
        project_id = str(data.get("project_id", "")).strip()
        with self._lock:
            self._project_repository_binding(actor_id, project_id, profile_id, repository_id)
            profile = self._active_gitlab_profile(profile_id)
            credential = self._active_credential(profile.credential_ref_id)
            repository = self._gitlab_repository(profile_id, repository_id)
            created = public_gitlab_branch(self.gitlab_client.create_branch(profile.base_url, self.secret_store.get(credential.secret_ref), repository_id, branch, ref))
            operation = VCSOperation(provider="gitlab", profile_id=profile_id, repository_id=repository_id, operation_type="create_branch", branch=branch)
            operation.validate()
            operation.status = "completed"
            operation.external_id = f"branch:{created.get('name', branch)}"
            operation.result = {"repository_id": repository["id"], "repository_path": repository["path"], "branch": created}
            operation.id = self._id("vcs")
            stamp(operation)
            self.vcs_operations[operation.id] = operation
            self._audit(actor_id, "gitlab.branch.created", "vcs_operation", operation.id, {"profile_id": profile_id, "repository_id": repository_id, "branch": branch})
            return asdict(operation)

    def create_gitlab_merge_request(self, actor_id: str, profile_id: str, repository_id: str, data: dict[str, Any]) -> dict[str, Any]:
        source_branch = str(data.get("source_branch", "")).strip()
        target_branch = str(data.get("target_branch", "")).strip()
        title = str(data.get("title", "")).strip()
        project_id = str(data.get("project_id", "")).strip()
        with self._lock:
            self._project_repository_binding(actor_id, project_id, profile_id, repository_id)
            profile = self._active_gitlab_profile(profile_id)
            credential = self._active_credential(profile.credential_ref_id)
            repository = self._gitlab_repository(profile_id, repository_id)
            operation = VCSOperation(
                provider="gitlab",
                profile_id=profile_id,
                repository_id=repository_id,
                operation_type="open_merge_request",
                source_branch=source_branch,
                target_branch=target_branch,
                title=title,
            )
            operation.validate()
            try:
                merge_request = self.gitlab_client.create_merge_request(
                    profile.base_url,
                    self.secret_store.get(credential.secret_ref),
                    repository_id,
                    source_branch,
                    target_branch,
                    title,
                )
            except Exception as exc:
                operation.status = "failed"
                operation.result = {"error": getattr(exc, "code", "gitlab_error")}
                operation.id = self._id("vcs")
                stamp(operation)
                self.vcs_operations[operation.id] = operation
                self._audit(actor_id, "gitlab.merge_request.failed", "vcs_operation", operation.id, {"profile_id": profile_id, "repository_id": repository_id})
                raise
            operation.status = "completed"
            operation.external_id = str(merge_request.get("iid", ""))
            operation.result = {"repository_id": repository["id"], "repository_path": repository["path"], "merge_request": merge_request}
            operation.id = self._id("vcs")
            stamp(operation)
            self.vcs_operations[operation.id] = operation
            self._audit(actor_id, "gitlab.merge_request.created", "vcs_operation", operation.id, {"profile_id": profile_id, "repository_id": repository_id, "iid": operation.external_id})
            return asdict(operation)

    def get_gitlab_merge_request(self, actor_id: str, project_id: str, profile_id: str, repository_id: str, merge_request_iid: str) -> dict[str, Any]:
        with self._lock:
            self._project_repository_binding(actor_id, project_id, profile_id, repository_id)
            profile = self._active_gitlab_profile(profile_id)
            credential = self._active_credential(profile.credential_ref_id)
            repository = self._gitlab_repository(profile_id, repository_id)
            merge_request = self.gitlab_client.get_merge_request(profile.base_url, self.secret_store.get(credential.secret_ref), repository_id, merge_request_iid)
            self._audit(actor_id, "gitlab.merge_request.read", "gitlab_repository", repository_id, {"profile_id": profile_id, "iid": str(merge_request_iid)})
            return {"repository": repository, "merge_request": merge_request}

    def create_vcs_operation(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        operation = VCSOperation(**pick(data, VCSOperation))
        operation.validate()
        with self._lock:
            repository = self._gitlab_repository(operation.profile_id, operation.repository_id)
            operation.status = "completed"
            operation.external_id = operation.external_id or self._vcs_external_id(operation)
            operation.result = {
                "adapter": "local_stub",
                "repository_id": repository["id"],
                "repository_path": repository["path"],
                "web_url": repository["web_url"],
            }
            operation.id = self._id("vcs")
            stamp(operation)
            self.vcs_operations[operation.id] = operation
            self._audit(
                actor_id,
                "vcs.operation.created",
                "vcs_operation",
                operation.id,
                {"provider": operation.provider, "profile_id": operation.profile_id, "repository_id": operation.repository_id, "operation_type": operation.operation_type},
            )
            return asdict(operation)

    def list_vcs_operations(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(operation) for operation in self.vcs_operations.values()]

    def ingest_vcs_webhook_event(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        event = VCSWebhookEvent(**pick(data, VCSWebhookEvent))
        event.validate()
        with self._lock:
            profile = self._gitlab_profile(event.profile_id)
            authenticity_token = str(data.get("authenticity_token", ""))
            if not profile.webhook_secret_ref or not authenticity_token or not self.secret_store.verify(profile.webhook_secret_ref, authenticity_token):
                raise InvalidInput("webhook authenticity token is invalid")
            if event.repository_id:
                self._gitlab_repository(event.profile_id, event.repository_id)
            event.payload = redact_sensitive_payload(event.payload)
            event.id = self._id("whk")
            stamp(event)
            self.vcs_webhook_events[event.id] = event
            self._audit(
                actor_id,
                "vcs.webhook.received",
                "vcs_webhook_event",
                event.id,
                {"provider": event.provider, "profile_id": event.profile_id, "repository_id": event.repository_id, "event_type": event.event_type},
            )
            return asdict(event)

    def list_vcs_webhook_events(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(event) for event in self.vcs_webhook_events.values()]

    def create_agent(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        agent = Agent(**pick(data, Agent))
        agent.validate()
        with self._lock:
            self._validate_agent_refs(agent)
            if any(existing.name.lower() == agent.name.lower() for existing in self.agents.values()):
                raise Conflict("agent name already exists")
            agent.id = self._id("agt")
            agent.capabilities = unique(agent.capabilities)
            agent.skill_ids = unique(agent.skill_ids)
            stamp(agent)
            self.agents[agent.id] = agent
            self._audit(actor_id, "agent.created", "agent", agent.id, {"kind": agent.kind})
            return asdict(agent)

    def list_agents(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(agent) for agent in self.agents.values()]

    def update_agent(self, actor_id: str, agent_id: str, data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            agent = self._agent(agent_id)
            if "name" in data and any(existing.id != agent_id and existing.name.lower() == str(data["name"]).lower() for existing in self.agents.values()):
                raise Conflict("agent name already exists")
            for key in ("name", "kind", "description", "status", "capabilities", "skill_ids", "model_provider_id"):
                if key in data:
                    setattr(agent, key, data[key])
            agent.capabilities = unique(agent.capabilities)
            agent.skill_ids = unique(agent.skill_ids)
            self._validate_agent_refs(agent)
            agent.validate()
            agent.updated_at = now_utc()
            self._audit(actor_id, "agent.updated", "agent", agent.id, {"status": agent.status})
            return asdict(agent)

    def delete_agent(self, actor_id: str, agent_id: str) -> dict[str, str]:
        with self._lock:
            agent = self.agents.pop(agent_id, None)
            if agent is None:
                raise NotFound("agent not found")
            self._audit(actor_id, "agent.deleted", "agent", agent_id, {"name": agent.name})
            return {"status": "deleted"}

    def create_skill(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        skill = Skill(**pick(data, Skill))
        skill.validate()
        with self._lock:
            if skill.package_file_id and skill.package_file_id not in self.files:
                raise NotFound("package file not found")
            if any(existing.name.lower() == skill.name.lower() and existing.version == skill.version for existing in self.skills.values()):
                raise Conflict("skill version already exists")
            skill.id = self._id("skl")
            skill.capabilities = unique(skill.capabilities)
            stamp(skill)
            self.skills[skill.id] = skill
            self._audit(actor_id, "skill.created", "skill", skill.id, {"name": skill.name, "version": skill.version})
            return asdict(skill)

    def list_skills(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(skill) for skill in self.skills.values()]

    def update_skill(self, actor_id: str, skill_id: str, data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            skill = self._skill(skill_id)
            if "package_file_id" in data and data["package_file_id"] and data["package_file_id"] not in self.files:
                raise NotFound("package file not found")
            for key in ("name", "version", "runtime", "description", "status", "capabilities", "package_file_id"):
                if key in data:
                    setattr(skill, key, data[key])
            if any(existing.id != skill_id and existing.name.lower() == skill.name.lower() and existing.version == skill.version for existing in self.skills.values()):
                raise Conflict("skill version already exists")
            skill.capabilities = unique(skill.capabilities)
            skill.validate()
            skill.updated_at = now_utc()
            self._audit(actor_id, "skill.updated", "skill", skill.id, {"status": skill.status})
            return asdict(skill)

    def delete_skill(self, actor_id: str, skill_id: str) -> dict[str, str]:
        with self._lock:
            if any(skill_id in agent.skill_ids for agent in self.agents.values()):
                raise Conflict("skill is used by an agent")
            skill = self.skills.pop(skill_id, None)
            if skill is None:
                raise NotFound("skill not found")
            self._audit(actor_id, "skill.deleted", "skill", skill_id, {"name": skill.name, "version": skill.version})
            return {"status": "deleted"}

    def create_model_provider(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        provider = ModelProvider(**pick(data, ModelProvider))
        provider.validate()
        with self._lock:
            credential = self._credential(provider.credential_ref_id)
            if credential.provider != "model_provider":
                raise InvalidInput("model providers require a model_provider credential")
            if any(existing.name.lower() == provider.name.lower() for existing in self.model_providers.values()):
                raise Conflict("model provider name already exists")
            provider.id = self._id("mdl")
            provider.models = unique(provider.models)
            stamp(provider)
            self.model_providers[provider.id] = provider
            self._audit(actor_id, "model_provider.created", "model_provider", provider.id, {"provider": provider.provider, "credential_ref_id": provider.credential_ref_id})
            return asdict(provider)

    def list_model_providers(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(provider) for provider in self.model_providers.values()]

    def update_model_provider(self, actor_id: str, provider_id: str, data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            provider = self._model_provider(provider_id)
            if "credential_ref_id" in data:
                credential = self._credential(str(data["credential_ref_id"]))
                if credential.provider != "model_provider":
                    raise InvalidInput("model providers require a model_provider credential")
            if "name" in data and any(existing.id != provider_id and existing.name.lower() == str(data["name"]).lower() for existing in self.model_providers.values()):
                raise Conflict("model provider name already exists")
            for key in ("provider", "name", "credential_ref_id", "base_url", "models", "status"):
                if key in data:
                    setattr(provider, key, data[key])
            provider.models = unique(provider.models)
            provider.validate()
            provider.updated_at = now_utc()
            self._audit(actor_id, "model_provider.updated", "model_provider", provider.id, {"status": provider.status})
            return asdict(provider)

    def delete_model_provider(self, actor_id: str, provider_id: str) -> dict[str, str]:
        with self._lock:
            if any(agent.model_provider_id == provider_id for agent in self.agents.values()):
                raise Conflict("model provider is used by an agent")
            provider = self.model_providers.pop(provider_id, None)
            if provider is None:
                raise NotFound("model provider not found")
            self._audit(actor_id, "model_provider.deleted", "model_provider", provider_id, {"name": provider.name})
            return {"status": "deleted"}

    def create_workflow(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        workflow = WorkflowDefinition(**pick(data, WorkflowDefinition))
        workflow.validate()
        with self._lock:
            if workflow.project_id and workflow.project_id not in self.projects:
                raise NotFound("project not found")
            if any(existing.name.lower() == workflow.name.lower() for existing in self.workflows.values()):
                raise Conflict("workflow name already exists")
            workflow.id = self._id("wfl")
            stamp(workflow)
            self.workflows[workflow.id] = workflow
            self._audit(actor_id, "workflow.created", "workflow", workflow.id, {"status": workflow.status})
            return asdict(workflow)

    def list_workflows(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(workflow) for workflow in self.workflows.values()]

    def update_workflow(self, actor_id: str, workflow_id: str, data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            workflow = self._workflow(workflow_id)
            if "project_id" in data and data["project_id"] and data["project_id"] not in self.projects:
                raise NotFound("project not found")
            if "name" in data and any(existing.id != workflow_id and existing.name.lower() == str(data["name"]).lower() for existing in self.workflows.values()):
                raise Conflict("workflow name already exists")
            candidate = WorkflowDefinition(**asdict(workflow))
            for key in ("name", "description", "project_id", "status", "active_version_id"):
                if key in data:
                    setattr(candidate, key, data[key])
            if candidate.active_version_id:
                active_version = self._workflow_version(candidate.active_version_id)
                if active_version.workflow_id != candidate.id:
                    raise Conflict("active version belongs to another workflow")
            candidate.validate()
            for key in ("name", "description", "project_id", "status", "active_version_id"):
                setattr(workflow, key, getattr(candidate, key))
            workflow.updated_at = now_utc()
            self._audit(actor_id, "workflow.updated", "workflow", workflow.id, {"status": workflow.status})
            return asdict(workflow)

    def delete_workflow(self, actor_id: str, workflow_id: str) -> dict[str, str]:
        with self._lock:
            workflow = self._delete_workflow_cascade(workflow_id)
            if workflow is None:
                raise NotFound("workflow not found")
            self._audit(actor_id, "workflow.deleted", "workflow", workflow_id, {"name": workflow.name})
            return {"status": "deleted"}

    def create_workflow_version(self, actor_id: str, workflow_id: str, data: dict[str, Any]) -> dict[str, Any]:
        payload = {**data, "workflow_id": workflow_id}
        version = WorkflowVersion(**pick(payload, WorkflowVersion))
        version.validate()
        with self._lock:
            workflow = self._workflow(workflow_id)
            self._validate_workflow_version_refs(version)
            if any(existing.workflow_id == workflow_id and existing.version == version.version for existing in self.workflow_versions.values()):
                raise Conflict("workflow version already exists")
            version.id = self._id("wfv")
            stamp(version)
            self.workflow_versions[version.id] = version
            if not workflow.active_version_id:
                workflow.active_version_id = version.id
                workflow.updated_at = version.updated_at
            self._audit(actor_id, "workflow.version.created", "workflow_version", version.id, {"workflow_id": workflow_id, "version": version.version})
            return asdict(version)

    def list_workflow_versions(self, workflow_id: str) -> list[dict[str, Any]]:
        with self._lock:
            self._workflow(workflow_id)
            return [asdict(version) for version in self.workflow_versions.values() if version.workflow_id == workflow_id]

    def update_workflow_version(self, actor_id: str, workflow_id: str, version_id: str, data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._workflow(workflow_id)
            version = self._workflow_version(version_id)
            if version.workflow_id != workflow_id:
                raise NotFound("workflow version not found")
            for key in ("version", "nodes", "edges", "status"):
                if key in data:
                    setattr(version, key, data[key])
            version.validate()
            self._validate_workflow_version_refs(version)
            version.updated_at = now_utc()
            self._audit(actor_id, "workflow.version.updated", "workflow_version", version.id, {"status": version.status})
            return asdict(version)

    def create_workflow_run(self, actor_id: str, workflow_id: str, data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            workflow = self._workflow(workflow_id)
            version_id = str(data.get("workflow_version_id") or workflow.active_version_id)
            if not version_id:
                raise InvalidInput("workflow has no active version")
            version = self._workflow_version(version_id)
            if version.workflow_id != workflow.id:
                raise Conflict("workflow version belongs to another workflow")
            ordered_nodes = self._ordered_workflow_nodes(version)
            if not ordered_nodes:
                raise InvalidInput("workflow active version has no nodes")
            run = WorkflowRun(workflow_id=workflow.id, workflow_version_id=version.id, trigger_type=str(data.get("trigger_type") or "manual"))
            run.validate()
            run.id = self._id("wfr")
            stamp(run)
            self.workflow_runs[run.id] = run
            predecessors_by_node_id = self._workflow_predecessor_snapshot(version)
            for sequence, node in enumerate(ordered_nodes, start=1):
                step = WorkflowStepRun(
                    workflow_run_id=run.id,
                    workflow_id=workflow.id,
                    workflow_version_id=version.id,
                    node_id=str(node["id"]),
                    node_type=str(node["type"]),
                    step_type=self._workflow_step_type(str(node["type"])),
                    sequence=sequence,
                    name=str(node.get("name", "")),
                    agent_id=str(node.get("agent_id", "")),
                    skill_id=str(node.get("skill_id", "")),
                    model_provider_id=str(node.get("model_provider_id", "")),
                    predecessor_node_ids=predecessors_by_node_id[str(node["id"])],
                    input=dict(node.get("config", {})) if isinstance(node.get("config", {}), dict) else {},
                )
                step.validate()
                step.id = self._id("wfs")
                stamp(step)
                self.workflow_step_runs[step.id] = step
            self._audit(actor_id, "workflow.run.created", "workflow_run", run.id, {"workflow_id": workflow.id, "workflow_version_id": version.id, "step_count": len(ordered_nodes)})
            response = self._workflow_run_response(run)
            if data.get("start") is True:
                return self.start_workflow_run(actor_id, run.id)
            return response

    def list_workflow_runs(self, workflow_id: str = "") -> list[dict[str, Any]]:
        with self._lock:
            runs = self.workflow_runs.values()
            if workflow_id:
                self._workflow(workflow_id)
                runs = [run for run in runs if run.workflow_id == workflow_id]
            return [self._workflow_run_response(run) for run in runs]

    def start_workflow_run(self, actor_id: str, run_id: str) -> dict[str, Any]:
        with self._lock:
            run = self._workflow_run(run_id)
            if run.status != "created":
                raise Conflict("workflow run cannot be started from current status")
            stamp_time = now_utc()
            run.status = "running"
            run.started_at = stamp_time
            run.updated_at = stamp_time
            for step in self._steps_for_run(run.id):
                if step.step_type == "trigger":
                    step.status = "completed"
                    step.started_at = stamp_time
                    step.completed_at = stamp_time
                    step.updated_at = stamp_time
            self._audit(actor_id, "workflow.run.started", "workflow_run", run.id, {"workflow_id": run.workflow_id, "workflow_version_id": run.workflow_version_id})
            self._refresh_workflow_run_status(run)
            self._dispatch_ready_agent_steps(actor_id, run)
            return self._workflow_run_response(run)

    def update_workflow_step_run(self, actor_id: str, run_id: str, step_run_id: str, data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            run = self._workflow_run(run_id)
            step = self._workflow_step_run(step_run_id)
            if step.workflow_run_id != run.id:
                raise NotFound("workflow step run not found")
            if step.step_type == "trigger":
                raise InvalidInput("trigger step runs are managed by workflow start")
            if run.status != "running":
                raise Conflict("workflow run is not active")
            next_status = str(data.get("status", "")).strip()
            if not next_status:
                raise InvalidInput("workflow step updates require status")
            self._validate_step_transition(step, next_status)
            self._validate_step_predecessors(run, step)
            stamp_time = now_utc()
            if next_status == "running" and not step.started_at:
                step.started_at = stamp_time
            if next_status in {"completed", "failed", "skipped"}:
                step.completed_at = stamp_time
                if not step.started_at:
                    step.started_at = stamp_time
            step.status = next_status
            if "output" in data:
                if not isinstance(data["output"], dict):
                    raise InvalidInput("workflow step output must be an object")
                step.output = self._sanitize_runtime_capture(data["output"])
            if "error" in data:
                step.error = self._sanitize_runtime_error(str(data["error"]))
            step.updated_at = stamp_time
            if step.step_type == "agent" and next_status in {"completed", "failed", "skipped"}:
                self._close_active_runtime_tasks_for_step(step, next_status, stamp_time)
            self._audit(actor_id, "workflow.step.updated", "workflow_step_run", step.id, {"workflow_run_id": run.id, "step_type": step.step_type, "status": step.status})
            self._refresh_workflow_run_status(run)
            self._dispatch_ready_agent_steps(actor_id, run)
            return self._workflow_run_response(run)

    def list_runtime_tasks(self, status: str = "") -> list[dict[str, Any]]:
        with self._lock:
            self._expire_runtime_task_leases("system")
            tasks = self.workflow_runtime_tasks.values()
            if status:
                tasks = [task for task in tasks if task.status == status]
            return [self._runtime_task_response(task, include_attempt_token=False) for task in sorted(tasks, key=lambda task: (task.created_at, task.id))]

    def claim_runtime_task(self, actor_id: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            data = data or {}
            self._expire_runtime_task_leases(actor_id)
            agent_id = str(data.get("agent_id", "")).strip()
            worker_id = str(data.get("worker_id", "") or actor_id).strip()
            lease_seconds = self._runtime_non_negative_int(data, "lease_seconds", default=60)
            queued = [task for task in self.workflow_runtime_tasks.values() if task.status == "queued" and (not agent_id or task.agent_id == agent_id)]
            if not queued:
                raise NotFound("runtime task not found")
            task = sorted(queued, key=lambda candidate: (candidate.created_at, candidate.id))[0]
            run = self._workflow_run(task.workflow_run_id)
            step = self._workflow_step_run(task.workflow_step_run_id)
            if run.status != "running" or step.status != "running":
                raise Conflict("runtime task is not claimable")
            stamp_time = now_utc()
            task.status = "running"
            task.claimed_at = task.claimed_at or stamp_time
            task.worker_id = worker_id
            task.heartbeat_at = stamp_time
            task.lease_expires_at = self._runtime_lease_expires_at(stamp_time, lease_seconds)
            task.updated_at = stamp_time
            self._audit(actor_id, "workflow.runtime_task.claimed", "workflow_runtime_task", task.id, {"workflow_run_id": run.id, "workflow_step_run_id": step.id, "status": task.status, "attempt": task.attempt, "worker_id": worker_id})
            return self._runtime_task_response(task, include_attempt_token=True)

    def callback_runtime_task(self, actor_id: str, task_id: str, data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            task = self._runtime_task(task_id)
            run = self._workflow_run(task.workflow_run_id)
            step = self._workflow_step_run(task.workflow_step_run_id)
            self._validate_runtime_callback_token(task, data)
            next_status = str(data.get("status", "")).strip()
            if next_status not in {"running", "completed", "failed"}:
                raise InvalidInput("runtime callback status must be running, completed, or failed")
            callback_output = self._runtime_callback_output(data)
            callback_error = self._runtime_callback_error(data)
            if task.status in {"completed", "failed", "timed_out", "cancelled"}:
                if self._runtime_callback_is_idempotent(task, next_status, callback_output, callback_error):
                    return self._workflow_run_response(run)
                raise Conflict("runtime task cannot transition from current status")
            if run.status != "running" or step.status != "running":
                raise Conflict("runtime task workflow run is not active")
            stamp_time = now_utc()
            if next_status == "running":
                if task.status not in {"queued", "running"}:
                    raise Conflict("runtime task cannot transition from current status")
                lease_seconds = self._runtime_non_negative_int(data, "lease_seconds", default=0)
                task.status = "running"
                task.claimed_at = task.claimed_at or stamp_time
                task.heartbeat_at = stamp_time
                if lease_seconds:
                    task.lease_expires_at = self._runtime_lease_expires_at(stamp_time, lease_seconds)
                task.updated_at = stamp_time
                self._audit(actor_id, "workflow.runtime_task.updated", "workflow_runtime_task", task.id, {"workflow_run_id": run.id, "workflow_step_run_id": step.id, "status": task.status, "attempt": task.attempt})
                return self._workflow_run_response(run)
            if task.status not in {"queued", "running"}:
                raise Conflict("runtime task cannot transition from current status")
            if callback_output is not None:
                task.output = callback_output
            if callback_error is not None:
                task.error = callback_error
            task.status = next_status
            task.completed_at = stamp_time
            task.updated_at = stamp_time
            if next_status == "completed":
                step.status = "completed"
                step.output = task.output
                step.completed_at = stamp_time
                step.updated_at = stamp_time
            else:
                should_retry = bool(data.get("retry") is True) and task.attempt < task.max_attempts
                if should_retry:
                    step.status = "pending"
                    step.error = task.error
                    step.updated_at = stamp_time
                    self._queue_runtime_task(actor_id, run, step, task.attempt + 1, task.max_attempts, task.timeout_seconds)
                else:
                    step.status = "failed"
                    step.error = task.error
                    step.completed_at = stamp_time
                    step.updated_at = stamp_time
            self._audit(actor_id, "workflow.runtime_task.callback", "workflow_runtime_task", task.id, {"workflow_run_id": run.id, "workflow_step_run_id": step.id, "status": task.status, "attempt": task.attempt})
            self._refresh_workflow_run_status(run)
            self._dispatch_ready_agent_steps(actor_id, run)
            return self._workflow_run_response(run)

    def timeout_runtime_task(self, actor_id: str, task_id: str) -> dict[str, Any]:
        with self._lock:
            task = self._runtime_task(task_id)
            if task.status in {"completed", "failed", "timed_out", "cancelled"}:
                return self._workflow_run_response(self._workflow_run(task.workflow_run_id))
            run = self._workflow_run(task.workflow_run_id)
            step = self._workflow_step_run(task.workflow_step_run_id)
            if run.status != "running" or step.status != "running":
                raise Conflict("runtime task workflow run is not active")
            stamp_time = now_utc()
            task.status = "timed_out"
            task.error = task.error or "runtime task timed out"
            task.completed_at = stamp_time
            task.updated_at = stamp_time
            step.status = "failed"
            step.error = task.error
            step.completed_at = stamp_time
            step.updated_at = stamp_time
            self._audit(actor_id, "workflow.runtime_task.timed_out", "workflow_runtime_task", task.id, {"workflow_run_id": run.id, "workflow_step_run_id": step.id, "status": task.status, "attempt": task.attempt})
            self._refresh_workflow_run_status(run)
            return self._workflow_run_response(run)

    def cancel_workflow_run(self, actor_id: str, run_id: str) -> dict[str, Any]:
        with self._lock:
            run = self._workflow_run(run_id)
            if run.status in {"completed", "failed", "cancelled"}:
                raise Conflict("workflow run cannot be cancelled from current status")
            stamp_time = now_utc()
            run.status = "cancelled"
            run.completed_at = stamp_time
            run.updated_at = stamp_time
            for step in self._steps_for_run(run.id):
                if step.status in {"pending", "running"}:
                    step.status = "skipped" if step.step_type != "manual" else "failed"
                    step.completed_at = stamp_time
                    step.updated_at = stamp_time
            for task in self.workflow_runtime_tasks.values():
                if task.workflow_run_id == run.id and task.status in {"queued", "running"}:
                    task.status = "cancelled"
                    task.completed_at = stamp_time
                    task.updated_at = stamp_time
            self._audit(actor_id, "workflow.run.cancelled", "workflow_run", run.id, {"workflow_id": run.workflow_id, "workflow_version_id": run.workflow_version_id})
            return self._workflow_run_response(run)

    def create_test_case(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        test_case = TestCase(**pick(data, TestCase))
        test_case.validate()
        with self._lock:
            project = self._project(test_case.project_id)
            self._require_project_actor(actor_id, project)
            test_case.id = self._id("tca")
            stamp(test_case)
            self.test_cases[test_case.id] = test_case
            self._audit(actor_id, "test_case.created", "test_case", test_case.id, {"project_id": test_case.project_id, "case_type": test_case.case_type})
            return asdict(test_case)

    def list_test_cases(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(test_case) for test_case in self.test_cases.values()]

    def create_test_suite(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        suite = TestSuite(**pick(data, TestSuite))
        suite.validate()
        with self._lock:
            project = self._project(suite.project_id)
            self._require_project_actor(actor_id, project)
            suite.case_ids = unique(suite.case_ids)
            for case_id in suite.case_ids:
                test_case = self._test_case(case_id)
                if test_case.project_id != suite.project_id:
                    raise Conflict("test case belongs to another project")
            suite.id = self._id("tsu")
            stamp(suite)
            self.test_suites[suite.id] = suite
            self._audit(actor_id, "test_suite.created", "test_suite", suite.id, {"project_id": suite.project_id, "case_count": len(suite.case_ids)})
            return asdict(suite)

    def list_test_suites(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(suite) for suite in self.test_suites.values()]

    def create_test_run(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        run = TestRun(**pick(data, TestRun))
        run.validate()
        with self._lock:
            project = self._project(run.project_id)
            self._require_project_actor(actor_id, project)
            suite = self._test_suite(run.suite_id)
            if suite.project_id != run.project_id:
                raise Conflict("test suite belongs to another project")
            if run.environment_id:
                environment = self._environment(run.environment_id)
                if environment.project_id != run.project_id:
                    raise Conflict("environment belongs to another project")
            run.id = self._id("trn")
            stamp(run)
            self.test_runs[run.id] = run
            self._audit(actor_id, "test_run.created", "test_run", run.id, {"project_id": run.project_id, "suite_id": run.suite_id, "status": run.status})
            return asdict(run)

    def list_test_runs(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(run) for run in self.test_runs.values()]

    def update_test_run(self, actor_id: str, run_id: str, data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            run = self._test_run(run_id)
            project = self._project(run.project_id)
            self._require_project_actor(actor_id, project)
            for key in ("status", "results"):
                if key in data:
                    setattr(run, key, data[key])
            run.validate()
            run.updated_at = now_utc()
            self._audit(actor_id, "test_run.updated", "test_run", run.id, {"status": run.status})
            return asdict(run)

    def create_report(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        report = Report(**pick(data, Report))
        report.validate()
        with self._lock:
            project = self._project(report.project_id)
            self._require_project_actor(actor_id, project)
            run = None
            if report.test_run_id:
                run = self._test_run(report.test_run_id)
                if run.project_id != report.project_id:
                    raise Conflict("test run belongs to another project")
            report.file_ids = unique(report.file_ids)
            for file_id in report.file_ids:
                self._validate_report_file(report, project, run, file_id)
            report.id = self._id("rpt")
            stamp(report)
            self.reports[report.id] = report
            self._audit(actor_id, "report.created", "report", report.id, {"project_id": report.project_id, "report_type": report.report_type})
            return asdict(report)

    def ingest_test_run_artifacts(self, actor_id: str, test_run_id: str, data: dict[str, Any]) -> dict[str, Any]:
        artifacts = data.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            raise InvalidInput("artifact ingest requires artifacts")
        with self._lock:
            run = self._test_run(test_run_id)
            project = self._project(run.project_id)
            self._require_project_actor(actor_id, project)
            if run.environment_id:
                environment = self._environment(run.environment_id)
                if environment.project_id != project.id:
                    raise Conflict("environment belongs to another project")
            staged_files: list[tuple[FileObject, bytes, dict[str, Any]]] = []
            summaries: list[dict[str, Any]] = []
            parse_errors: list[dict[str, str]] = []
            for raw_artifact in artifacts:
                if not isinstance(raw_artifact, dict):
                    raise InvalidInput("artifact entries must be objects")
                content = self._decode_file_content(raw_artifact)
                file_object = FileObject(
                    filename=str(raw_artifact.get("filename", "") or ""),
                    content_type=str(raw_artifact.get("content_type", "") or "application/octet-stream"),
                    size_bytes=len(content),
                    owner_id=actor_id,
                    resource_type="test_run",
                    resource_id=run.id,
                    module="reports",
                    status="available",
                    checksum=f"sha256:{hashlib.sha256(content).hexdigest()}",
                )
                file_object.validate()
                file_object.id = self._id("fil")
                file_object.storage_key = self._new_storage_key()
                stamp(file_object)
                parsed = self._parse_report_artifact(file_object, content, str(raw_artifact.get("artifact_type", "") or ""))
                staged_files.append((file_object, content, parsed))
                if parsed.get("parse_status") == "failed":
                    parse_errors.append({"file_id": file_object.id, "filename": file_object.filename, "error": str(parsed.get("error", ""))})
                elif parsed.get("format"):
                    summaries.append(parsed)
            summary = self._combine_report_summaries(summaries, parse_errors)
            file_ids = [file_object.id for file_object, _, _ in staged_files]
            report = Report(
                project_id=project.id,
                title=str(data.get("title", "") or f"Test run {run.id} artifact report"),
                report_type=str(data.get("report_type", "") or "test"),
                test_run_id=run.id,
                file_ids=file_ids,
                summary=summary,
                status="failed" if parse_errors else "published",
            )
            report.validate()
            report.id = self._id("rpt")
            stamp(report)
            stored_keys: list[str] = []
            try:
                for file_object, content, _ in staged_files:
                    self.storage.put(file_object.storage_key, content)
                    stored_keys.append(file_object.storage_key)
            except Exception:
                for storage_key in stored_keys:
                    try:
                        self.storage.delete(storage_key)
                    except Exception:
                        pass
                raise
            for file_object, _, _ in staged_files:
                self.files[file_object.id] = file_object
                self._audit(actor_id, "file.uploaded", "file", file_object.id, self._file_audit_metadata(file_object))
            self.reports[report.id] = report
            run.status = self._test_run_status_from_summary(summary)
            run.results = self._test_run_results_from_summary(summary)
            run.updated_at = now_utc()
            gate = self._upsert_ingest_quality_gate(actor_id, project.id, report, summary)
            self._audit(actor_id, "test_run.updated", "test_run", run.id, {"status": run.status})
            self._audit(actor_id, "report.ingested", "report", report.id, {"project_id": report.project_id, "test_run_id": run.id, "file_count": len(file_ids), "parse_status": summary["parse_status"]})
            return {"report": asdict(report), "files": [self._public_file(self.files[file_id]) for file_id in file_ids], "test_run": asdict(run), "quality_gate": asdict(gate)}

    def list_reports(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(report) for report in self.reports.values()]

    def create_quality_gate(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        gate = QualityGate(**pick(data, QualityGate))
        gate.validate()
        with self._lock:
            project = self._project(gate.project_id)
            self._require_project_actor(actor_id, project)
            if gate.last_report_id:
                report = self._report(gate.last_report_id)
                if report.project_id != gate.project_id:
                    raise Conflict("report belongs to another project")
            gate.id = self._id("qgt")
            stamp(gate)
            self.quality_gates[gate.id] = gate
            self._audit(actor_id, "quality_gate.created", "quality_gate", gate.id, {"project_id": gate.project_id, "status": gate.status})
            return asdict(gate)

    def list_quality_gates(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(gate) for gate in self.quality_gates.values()]

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

    def _file(self, file_id: str) -> FileObject:
        if file_id not in self.files:
            raise NotFound("file not found")
        return self.files[file_id]

    def _validate_asset_parent(self, asset_id: str, parent_id: str) -> None:
        seen = {asset_id}
        current_id = parent_id
        while current_id:
            if current_id in seen:
                raise Conflict("asset parent hierarchy cannot contain cycles")
            seen.add(current_id)
            current = self.assets.get(current_id)
            if current is None:
                raise NotFound("parent asset not found")
            current_id = current.parent_id

    def _validate_topology_file(self, resource_type: str, resource_id: str, file_id: str) -> None:
        file_object = self._file(file_id)
        if file_object.status == "deleted":
            raise Conflict("file is deleted")
        if file_object.resource_type and file_object.resource_type != resource_type:
            raise Conflict("file resource type does not match")
        if file_object.resource_id and file_object.resource_id != resource_id:
            raise Conflict("file resource id does not match")

    def _validate_asset_files(self, asset: Asset) -> None:
        asset.file_ids = unique(asset.file_ids)
        for file_id in asset.file_ids:
            self._validate_topology_file("asset", asset.id, file_id)

    def _validate_environment_files(self, actor_id: str, environment: Environment) -> None:
        environment.file_ids = unique(environment.file_ids)
        for file_id in environment.file_ids:
            self._claim_or_validate_environment_file(actor_id, environment, file_id)

    def _claim_or_validate_environment_file(self, actor_id: str, environment: Environment, file_id: str) -> None:
        project = self._project(environment.project_id)
        self._require_project_actor(actor_id, project)
        file_object = self._file(file_id)
        if file_object.status == "deleted":
            raise Conflict("file is deleted")
        if file_object.owner_id != actor_id:
            raise PermissionDenied("actor cannot bind a file owned by another user")
        if file_object.resource_type == "environment" and file_object.resource_id == environment.id:
            return
        if not file_object.resource_type and not file_object.resource_id:
            file_object.resource_type = "environment"
            file_object.resource_id = environment.id
            file_object.module = file_object.module or "attachments"
            file_object.updated_at = now_utc()
            self._audit(actor_id, "environment.file.claimed", "file", file_object.id, {"environment_id": environment.id})
            return
        raise Conflict("file resource is outside the environment scope")

    def _validate_environment_member(self, project: Project, user_id: str) -> None:
        if not user_id or user_id not in self.users:
            raise NotFound("member not found")
        if user_id not in unique([project.owner_id, *project.member_ids]):
            raise Conflict("member belongs to another project")

    def _validate_environment_asset(self, project: Project, asset_id: str) -> None:
        if asset_id not in self.assets:
            raise NotFound("asset not found")
        if asset_id not in project.asset_ids:
            raise Conflict("asset is not bound to project")

    def _cleanup_asset_references(self, asset_id: str) -> None:
        for project in self.projects.values():
            if asset_id in project.asset_ids:
                project.asset_ids = [existing_id for existing_id in project.asset_ids if existing_id != asset_id]
                project.updated_at = now_utc()
        for environment in self.environments.values():
            if asset_id in environment.asset_ids:
                environment.asset_ids = [existing_id for existing_id in environment.asset_ids if existing_id != asset_id]
                environment.updated_at = now_utc()

    def _cleanup_file_references(self, file_id: str) -> None:
        for asset in self.assets.values():
            if file_id in asset.file_ids:
                asset.file_ids = [existing_id for existing_id in asset.file_ids if existing_id != file_id]
                asset.updated_at = now_utc()
        for environment in self.environments.values():
            if file_id in environment.file_ids:
                environment.file_ids = [existing_id for existing_id in environment.file_ids if existing_id != file_id]
                environment.updated_at = now_utc()

    def _matches_asset_filters(self, asset: Asset, filters: dict[str, str]) -> bool:
        if filters.get("category") and asset.category != filters["category"]:
            return False
        if filters.get("status") and asset.status != filters["status"]:
            return False
        if filters.get("parent_id") and asset.parent_id != filters["parent_id"]:
            return False
        if filters.get("capability") and filters["capability"] not in asset.capabilities:
            return False
        if filters.get("tag") and filters["tag"] not in asset.tags:
            return False
        project_id = filters.get("project_id", "")
        if project_id and (project_id not in self.projects or asset.id not in self.projects[project_id].asset_ids):
            return False
        environment_id = filters.get("environment_id", "")
        if environment_id and (environment_id not in self.environments or asset.id not in self.environments[environment_id].asset_ids):
            return False
        return True

    def _matches_environment_filters(self, environment: Environment, filters: dict[str, str]) -> bool:
        if filters.get("project_id") and environment.project_id != filters["project_id"]:
            return False
        if filters.get("type") and environment.type != filters["type"]:
            return False
        if filters.get("status") and environment.status != filters["status"]:
            return False
        if filters.get("asset_id") and filters["asset_id"] not in environment.asset_ids:
            return False
        if filters.get("member_id") and filters["member_id"] not in environment.member_ids:
            return False
        return True

    def _upload_session(self, session_id: str) -> UploadSession:
        if session_id not in self.upload_sessions:
            raise NotFound("upload session not found")
        return self.upload_sessions[session_id]

    def _credential(self, credential_id: str) -> CredentialReference:
        if credential_id not in self.credentials:
            raise NotFound("credential not found")
        return self.credentials[credential_id]

    def _gitlab_profile(self, profile_id: str) -> GitLabProfile:
        if profile_id not in self.gitlab_profiles:
            raise NotFound("gitlab profile not found")
        return self.gitlab_profiles[profile_id]

    def _active_credential(self, credential_id: str) -> CredentialReference:
        credential = self._credential(credential_id)
        if credential.status != "active":
            raise Conflict("credential is inactive")
        return credential

    def _active_gitlab_profile(self, profile_id: str) -> GitLabProfile:
        profile = self._gitlab_profile(profile_id)
        if profile.status != "active":
            raise Conflict("gitlab profile is inactive")
        return profile

    def _gitlab_repository(self, profile_id: str, repository_id: str) -> dict[str, str]:
        repositories = {repository["id"]: repository for repository in self.list_gitlab_repositories(profile_id)}
        if repository_id not in repositories:
            raise NotFound("repository not found for profile")
        return repositories[repository_id]

    def _project_repository_binding(self, actor_id: str, project_id: str, profile_id: str, repository_id: str) -> Project:
        if not actor_id or actor_id == "system":
            raise PermissionDenied("authenticated actor is required")
        if not project_id:
            raise InvalidInput("gitlab repository operations require project_id")
        project = self._project(project_id)
        self._require_project_actor(actor_id, project)
        for binding in project.repository_bindings:
            if binding.get("provider") == "gitlab" and binding.get("profile_id") == profile_id and binding.get("repository_id") == repository_id:
                return project
        raise Conflict("repository is not bound to project")

    def _require_project_actor(self, actor_id: str, project: Project) -> None:
        if not actor_id or actor_id == "system":
            raise PermissionDenied("authenticated actor is required")
        identity = self.service_identities.get(actor_id)
        if identity is not None and identity.status == "active":
            if project.id in identity.project_ids:
                return
            raise PermissionDenied("service identity is not bound to project")
        if actor_id not in unique([project.owner_id, *project.member_ids]):
            raise PermissionDenied("actor is not a project member")

    def _agent(self, agent_id: str) -> Agent:
        if agent_id not in self.agents:
            raise NotFound("agent not found")
        return self.agents[agent_id]

    def _skill(self, skill_id: str) -> Skill:
        if skill_id not in self.skills:
            raise NotFound("skill not found")
        return self.skills[skill_id]

    def _model_provider(self, provider_id: str) -> ModelProvider:
        if provider_id not in self.model_providers:
            raise NotFound("model provider not found")
        return self.model_providers[provider_id]

    def _workflow(self, workflow_id: str) -> WorkflowDefinition:
        if workflow_id not in self.workflows:
            raise NotFound("workflow not found")
        return self.workflows[workflow_id]

    def _workflow_version(self, version_id: str) -> WorkflowVersion:
        if version_id not in self.workflow_versions:
            raise NotFound("workflow version not found")
        return self.workflow_versions[version_id]

    def _workflow_run(self, run_id: str) -> WorkflowRun:
        if run_id not in self.workflow_runs:
            raise NotFound("workflow run not found")
        return self.workflow_runs[run_id]

    def _workflow_step_run(self, step_run_id: str) -> WorkflowStepRun:
        if step_run_id not in self.workflow_step_runs:
            raise NotFound("workflow step run not found")
        return self.workflow_step_runs[step_run_id]

    def _runtime_task(self, task_id: str) -> WorkflowRuntimeTask:
        if task_id not in self.workflow_runtime_tasks:
            raise NotFound("runtime task not found")
        return self.workflow_runtime_tasks[task_id]

    def _test_case(self, case_id: str) -> TestCase:
        if case_id not in self.test_cases:
            raise NotFound("test case not found")
        return self.test_cases[case_id]

    def _test_suite(self, suite_id: str) -> TestSuite:
        if suite_id not in self.test_suites:
            raise NotFound("test suite not found")
        return self.test_suites[suite_id]

    def _test_run(self, run_id: str) -> TestRun:
        if run_id not in self.test_runs:
            raise NotFound("test run not found")
        return self.test_runs[run_id]

    def _report(self, report_id: str) -> Report:
        if report_id not in self.reports:
            raise NotFound("report not found")
        return self.reports[report_id]

    def _validate_report_file(self, report: Report, project: Project, run: TestRun | None, file_id: str) -> None:
        file_object = self._file(file_id)
        if file_object.status != "available":
            raise Conflict("report file must be available")
        project_member_ids = set(unique([project.owner_id, *project.member_ids]))
        if not file_object.owner_id or file_object.owner_id not in project_member_ids:
            raise Conflict("report file owner is outside the project")
        allowed_resources = {("project", project.id)}
        if run is not None:
            allowed_resources.add(("test_run", run.id))
        if (file_object.resource_type, file_object.resource_id) not in allowed_resources:
            raise Conflict("report file resource is outside the report scope")
        if file_object.module not in {"reports", report.report_type}:
            raise Conflict("report file module is outside the report scope")

    def _validate_agent_refs(self, agent: Agent) -> None:
        for skill_id in agent.skill_ids:
            if skill_id not in self.skills:
                raise NotFound("skill not found")
        if agent.model_provider_id and agent.model_provider_id not in self.model_providers:
            raise NotFound("model provider not found")

    def _validate_workflow_version_refs(self, version: WorkflowVersion) -> None:
        for node in version.nodes:
            node_type = str(node.get("type", "")).strip()
            agent_id = str(node.get("agent_id", "")).strip()
            skill_id = str(node.get("skill_id", "")).strip()
            model_provider_id = str(node.get("model_provider_id", "")).strip()
            if node_type == "agent_task" and not agent_id:
                raise InvalidInput("agent_task nodes require agent_id")
            agent = self.agents.get(agent_id) if agent_id else None
            if agent_id and agent is None:
                raise NotFound("agent not found")
            if skill_id and skill_id not in self.skills:
                raise NotFound("skill not found")
            if model_provider_id and model_provider_id not in self.model_providers:
                raise NotFound("model provider not found")
            if agent is not None:
                if skill_id and skill_id not in agent.skill_ids:
                    raise Conflict("workflow node skill is not allowed by agent")
                if model_provider_id and model_provider_id != agent.model_provider_id:
                    raise Conflict("workflow node model provider is not allowed by agent")
            config = node.get("config", {})
            if node_type == "agent_task" and isinstance(config, dict):
                self._runtime_max_attempts(config)
                self._runtime_non_negative_int(config, "timeout_seconds", default=0)

    def _workflow_run_response(self, run: WorkflowRun) -> dict[str, Any]:
        response = asdict(run)
        response["steps"] = [asdict(step) for step in self._steps_for_run(run.id)]
        return response

    def _steps_for_run(self, run_id: str) -> list[WorkflowStepRun]:
        return sorted((step for step in self.workflow_step_runs.values() if step.workflow_run_id == run_id), key=lambda step: step.sequence)

    def _ordered_workflow_nodes(self, version: WorkflowVersion) -> list[dict[str, Any]]:
        nodes = [dict(node) for node in version.nodes]
        node_by_id = {str(node["id"]): node for node in nodes}
        edges = self._workflow_edge_pairs(version)
        incoming: dict[str, int] = {node_id: 0 for node_id in node_by_id}
        outgoing: dict[str, list[str]] = {node_id: [] for node_id in node_by_id}
        for from_node_id, to_node_id in edges:
            outgoing[from_node_id].append(to_node_id)
            incoming[to_node_id] += 1
        queue = [str(node["id"]) for node in nodes if incoming[str(node["id"])] == 0]
        ordered_ids: list[str] = []
        while queue:
            node_id = queue.pop(0)
            ordered_ids.append(node_id)
            for child_id in outgoing[node_id]:
                incoming[child_id] -= 1
                if incoming[child_id] == 0:
                    queue.append(child_id)
        if len(ordered_ids) != len(nodes):
            raise InvalidInput("workflow version edges must not contain cycles")
        return [node_by_id[node_id] for node_id in ordered_ids]

    def _workflow_edge_pairs(self, version: WorkflowVersion) -> list[tuple[str, str]]:
        return [(str(edge["from_node_id"]), str(edge["to_node_id"])) for edge in version.edges]

    def _workflow_predecessor_snapshot(self, version: WorkflowVersion) -> dict[str, list[str]]:
        predecessors = {str(node["id"]): [] for node in version.nodes}
        for from_node_id, to_node_id in self._workflow_edge_pairs(version):
            predecessors[to_node_id].append(from_node_id)
        return predecessors

    def _workflow_step_type(self, node_type: str) -> str:
        if node_type == "trigger":
            return "trigger"
        if node_type == "agent_task":
            return "agent"
        if node_type in {"approval", "manual", "manual_task"}:
            return "manual"
        return "result"

    def _delete_workflow_cascade(self, workflow_id: str) -> WorkflowDefinition | None:
        workflow = self.workflows.pop(workflow_id, None)
        if workflow is None:
            return None
        for run_id, run in list(self.workflow_runs.items()):
            if run.workflow_id == workflow_id:
                self.workflow_runs.pop(run_id, None)
        for step_id, step in list(self.workflow_step_runs.items()):
            if step.workflow_id == workflow_id:
                self.workflow_step_runs.pop(step_id, None)
        for task_id, task in list(self.workflow_runtime_tasks.items()):
            if task.workflow_id == workflow_id:
                self.workflow_runtime_tasks.pop(task_id, None)
        for version_id, version in list(self.workflow_versions.items()):
            if version.workflow_id == workflow_id:
                self.workflow_versions.pop(version_id, None)
        return workflow

    def _validate_step_transition(self, step: WorkflowStepRun, next_status: str) -> None:
        if next_status not in {"running", "completed", "failed", "skipped"}:
            raise InvalidInput("unsupported workflow step status")
        if step.step_type == "manual" and next_status == "skipped":
            raise InvalidInput("manual workflow step runs cannot be skipped")
        allowed = {
            "pending": {"running", "completed", "failed", "skipped"},
            "running": {"running", "completed", "failed", "skipped"},
            "completed": set(),
            "failed": set(),
            "skipped": set(),
        }
        if next_status not in allowed[step.status]:
            raise Conflict("workflow step cannot transition from current status")

    def _validate_step_predecessors(self, run: WorkflowRun, step: WorkflowStepRun) -> None:
        if not step.predecessor_node_ids:
            return
        steps_by_node_id = {candidate.node_id: candidate for candidate in self._steps_for_run(run.id)}
        for predecessor_node_id in step.predecessor_node_ids:
            predecessor = steps_by_node_id.get(predecessor_node_id)
            if predecessor is None:
                raise Conflict("workflow step predecessor is missing")
            if predecessor.step_type == "manual":
                if predecessor.status != "completed":
                    raise Conflict("manual predecessor step must be completed before downstream transition")
                continue
            if predecessor.status not in {"completed", "skipped"}:
                raise Conflict("predecessor step must be terminal before downstream transition")

    def _refresh_workflow_run_status(self, run: WorkflowRun) -> None:
        if run.status == "cancelled":
            return
        steps = self._steps_for_run(run.id)
        executable_steps = [step for step in steps if step.step_type != "trigger"]
        if any(step.status == "failed" for step in executable_steps):
            run.status = "failed"
            run.completed_at = run.completed_at or now_utc()
            run.updated_at = run.completed_at
            return
        if executable_steps and all(step.status in {"completed", "skipped"} for step in executable_steps):
            run.status = "completed"
            run.completed_at = run.completed_at or now_utc()
            run.updated_at = run.completed_at
            return
        if run.status != "created":
            run.status = "running"
            run.updated_at = now_utc()

    def _dispatch_ready_agent_steps(self, actor_id: str, run: WorkflowRun) -> None:
        if run.status != "running":
            return
        for step in self._steps_for_run(run.id):
            if step.step_type != "agent" or step.status != "pending":
                continue
            try:
                self._validate_step_predecessors(run, step)
            except Conflict:
                continue
            max_attempts = self._runtime_max_attempts(step.input)
            timeout_seconds = self._runtime_non_negative_int(step.input, "timeout_seconds", default=0)
            self._queue_runtime_task(actor_id, run, step, self._next_runtime_attempt(step), max(1, max_attempts), max(0, timeout_seconds))

    def _queue_runtime_task(self, actor_id: str, run: WorkflowRun, step: WorkflowStepRun, attempt: int, max_attempts: int, timeout_seconds: int) -> WorkflowRuntimeTask:
        if any(task.workflow_step_run_id == step.id and task.status in {"queued", "running"} for task in self.workflow_runtime_tasks.values()):
            raise Conflict("runtime task is already active for workflow step")
        stamp_time = now_utc()
        task = WorkflowRuntimeTask(
            workflow_run_id=run.id,
            workflow_step_run_id=step.id,
            workflow_id=run.workflow_id,
            workflow_version_id=run.workflow_version_id,
            node_id=step.node_id,
            agent_id=step.agent_id,
            skill_id=step.skill_id,
            model_provider_id=step.model_provider_id,
            attempt=attempt,
            max_attempts=max_attempts,
            timeout_seconds=timeout_seconds,
            input_summary=self._runtime_input_summary(step),
        )
        task.id = self._id("wrt")
        task.attempt_token = secrets.token_urlsafe(24)
        stamp(task)
        self.workflow_runtime_tasks[task.id] = task
        step.status = "running"
        step.started_at = step.started_at or stamp_time
        step.updated_at = stamp_time
        self._audit(actor_id, "workflow.runtime_task.dispatched", "workflow_runtime_task", task.id, {"workflow_run_id": run.id, "workflow_step_run_id": step.id, "status": task.status, "attempt": task.attempt})
        return task

    def _next_runtime_attempt(self, step: WorkflowStepRun) -> int:
        attempts = [task.attempt for task in self.workflow_runtime_tasks.values() if task.workflow_step_run_id == step.id]
        return max(attempts, default=0) + 1

    def _runtime_input_summary(self, step: WorkflowStepRun) -> dict[str, Any]:
        return redact_sensitive_payload(
            {
                "node_id": step.node_id,
                "agent_id": step.agent_id,
                "skill_id": step.skill_id,
                "model_provider_ref": step.model_provider_id,
                "binding_names": sorted(step.input.keys()),
            }
        )

    def _expire_runtime_task_leases(self, actor_id: str) -> None:
        stamp_time = now_utc()
        for task in self.workflow_runtime_tasks.values():
            if task.status != "running" or not task.lease_expires_at or not _is_past(task.lease_expires_at):
                continue
            run = self.workflow_runs.get(task.workflow_run_id)
            step = self.workflow_step_runs.get(task.workflow_step_run_id)
            if run is None or step is None or run.status != "running" or step.status != "running":
                continue
            previous_worker_id = task.worker_id
            task.status = "queued"
            task.worker_id = ""
            task.claimed_at = ""
            task.heartbeat_at = ""
            task.lease_expires_at = ""
            task.attempt_token = secrets.token_urlsafe(24)
            task.updated_at = stamp_time
            self._audit(actor_id, "workflow.runtime_task.lease_expired", "workflow_runtime_task", task.id, {"workflow_run_id": run.id, "workflow_step_run_id": step.id, "status": task.status, "attempt": task.attempt, "worker_id": previous_worker_id})

    def _runtime_lease_expires_at(self, stamp_time: str, lease_seconds: int) -> str:
        if lease_seconds <= 0:
            return ""
        return (datetime.fromisoformat(stamp_time) + timedelta(seconds=lease_seconds)).isoformat()

    def _validate_runtime_callback_token(self, task: WorkflowRuntimeTask, data: dict[str, Any]) -> None:
        token = str(data.get("attempt_token", "")).strip()
        if not token:
            raise InvalidInput("runtime callback requires attempt_token")
        if token != task.attempt_token:
            raise Conflict("runtime callback attempt_token does not match")

    def _runtime_callback_is_idempotent(self, task: WorkflowRuntimeTask, next_status: str, output: dict[str, Any] | None, error: str | None) -> bool:
        if next_status != task.status:
            return False
        if output is not None and output != task.output:
            return False
        if error is not None and error != task.error:
            return False
        return True

    def _close_active_runtime_tasks_for_step(self, step: WorkflowStepRun, step_status: str, stamp_time: str) -> None:
        task_status = {"completed": "completed", "failed": "failed", "skipped": "cancelled"}[step_status]
        for task in self.workflow_runtime_tasks.values():
            if task.workflow_step_run_id == step.id and task.status in {"queued", "running"}:
                task.status = task_status
                task.output = step.output if step_status == "completed" else task.output
                task.error = step.error if step_status == "failed" else task.error
                task.completed_at = stamp_time
                task.updated_at = stamp_time

    def _runtime_task_response(self, task: WorkflowRuntimeTask, *, include_attempt_token: bool) -> dict[str, Any]:
        response = asdict(task)
        if not include_attempt_token:
            response.pop("attempt_token", None)
        return response

    def _runtime_callback_output(self, data: dict[str, Any]) -> dict[str, Any] | None:
        if "output" not in data:
            return None
        if not isinstance(data["output"], dict):
            raise InvalidInput("runtime task output must be an object")
        return self._sanitize_runtime_capture(data["output"])

    def _runtime_callback_error(self, data: dict[str, Any]) -> str | None:
        if "error" not in data:
            return None
        return self._sanitize_runtime_error(str(data["error"]))

    def _sanitize_runtime_capture(self, value: Any) -> Any:
        redacted = redact_sensitive_payload(value)
        if isinstance(redacted, dict):
            return {str(key): self._sanitize_runtime_capture(item) for key, item in redacted.items()}
        if isinstance(redacted, list):
            return [self._sanitize_runtime_capture(item) for item in redacted]
        if isinstance(redacted, str) and self._looks_token_like(redacted):
            return "[REDACTED]"
        return redacted

    def _sanitize_runtime_error(self, value: str) -> str:
        return "[REDACTED]" if self._looks_token_like(value) else value

    def _looks_token_like(self, value: str) -> bool:
        lowered = value.lower()
        return any(marker in lowered for marker in ("token", "secret", "password", "api_key", "apikey", "key=", "key:"))

    def _runtime_max_attempts(self, data: dict[str, Any]) -> int:
        if "max_attempts" in data:
            return self._runtime_positive_int(data, "max_attempts")
        retries = self._runtime_non_negative_int(data, "retries", default=0)
        return retries + 1

    def _runtime_positive_int(self, data: dict[str, Any], key: str) -> int:
        value = self._runtime_non_negative_int(data, key, default=1)
        if value <= 0:
            raise InvalidInput(f"{key} must be a positive integer")
        return value

    def _runtime_non_negative_int(self, data: dict[str, Any], key: str, *, default: int) -> int:
        if key not in data or data[key] is None or data[key] == "":
            return default
        try:
            value = int(data[key])
        except (TypeError, ValueError) as exc:
            raise InvalidInput(f"{key} must be an integer") from exc
        if value < 0:
            raise InvalidInput(f"{key} must not be negative")
        return value

    def _id(self, prefix: str) -> str:
        self._ids += 1
        return f"{prefix}_{self._ids:06d}"

    def _vcs_external_id(self, operation: VCSOperation) -> str:
        if operation.operation_type == "create_branch":
            return f"branch:{operation.branch}"
        if operation.operation_type == "open_merge_request":
            return f"mr:{operation.source_branch}:{operation.target_branch}"
        return f"merge:{operation.external_id}"

    def _new_storage_key(self) -> str:
        return f"objects/{secrets.token_urlsafe(24)}"

    def _public_file(self, file_object: FileObject) -> dict[str, Any]:
        public = asdict(file_object)
        public.pop("storage_key", None)
        return public

    def _decode_file_content(self, data: dict[str, Any]) -> bytes:
        encoded = data.get("content_base64")
        if not isinstance(encoded, str) or not encoded:
            raise InvalidInput("file upload requires content_base64")
        if len(encoded) > ((MAX_FILE_UPLOAD_BYTES + 2) // 3) * 4:
            raise InvalidInput("file upload exceeds max size")
        try:
            content = base64.b64decode(encoded.encode("ascii"), validate=True)
        except (ValueError, UnicodeEncodeError) as exc:
            raise InvalidInput("content_base64 is invalid") from exc
        if len(content) > MAX_FILE_UPLOAD_BYTES:
            raise InvalidInput("file upload exceeds max size")
        return content

    def _parse_report_artifact(self, file_object: FileObject, content: bytes, artifact_type: str = "") -> dict[str, Any]:
        kind = artifact_type.strip().lower()
        filename = file_object.filename.lower()
        content_type = file_object.content_type.lower()
        if kind == "junit" or filename.endswith(".xml") or "junit" in content_type or content_type in {"application/xml", "text/xml"}:
            try:
                return self._parse_junit_summary(content)
            except (ET.ParseError, ValueError) as exc:
                return {"parse_status": "failed", "format": "junit", "error": str(exc)}
        if kind == "json" or filename.endswith(".json") or content_type == "application/json":
            try:
                decoded = json.loads(content.decode("utf-8"))
                if not isinstance(decoded, dict):
                    raise ValueError("json summary must be an object")
                return self._parse_json_report_summary(decoded)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
                return {"parse_status": "failed", "format": "json", "error": str(exc)}
        return {"parse_status": "skipped", "format": ""}

    def _parse_junit_summary(self, content: bytes) -> dict[str, Any]:
        root = ET.fromstring(content)
        suites = [root] if root.tag == "testsuite" else list(root.findall(".//testsuite"))
        if not suites and root.tag != "testsuites":
            raise ValueError("junit report requires testsuite or testsuites root")
        total = failures = errors = skipped = 0
        cases: list[dict[str, Any]] = []
        source = suites or [root]
        for suite in source:
            total += int(float(suite.attrib.get("tests", "0") or 0))
            failures += int(float(suite.attrib.get("failures", "0") or 0))
            errors += int(float(suite.attrib.get("errors", "0") or 0))
            skipped += int(float(suite.attrib.get("skipped", "0") or 0))
            for case in suite.findall("testcase"):
                status = "passed"
                if case.find("failure") is not None:
                    status = "failed"
                elif case.find("error") is not None:
                    status = "error"
                elif case.find("skipped") is not None:
                    status = "skipped"
                cases.append({"name": case.attrib.get("name", ""), "classname": case.attrib.get("classname", ""), "status": status})
        if total == 0 and cases:
            total = len(cases)
            failures = len([case for case in cases if case["status"] == "failed"])
            errors = len([case for case in cases if case["status"] == "error"])
            skipped = len([case for case in cases if case["status"] == "skipped"])
        passed = max(total - failures - errors - skipped, 0)
        return {"parse_status": "parsed", "format": "junit", "total": total, "passed": passed, "failed": failures, "errors": errors, "skipped": skipped, "cases": cases[:100]}

    def _parse_json_report_summary(self, data: dict[str, Any]) -> dict[str, Any]:
        total = int(data.get("total", data.get("tests", 0)) or 0)
        passed = int(data.get("passed", 0) or 0)
        failed = int(data.get("failed", data.get("failures", 0)) or 0)
        errors = int(data.get("errors", 0) or 0)
        skipped = int(data.get("skipped", 0) or 0)
        if total == 0:
            total = passed + failed + errors + skipped
        if passed == 0 and total:
            passed = max(total - failed - errors - skipped, 0)
        cases = data.get("cases", data.get("results", []))
        if cases is not None and not isinstance(cases, list):
            raise ValueError("json summary cases must be a list")
        return {"parse_status": "parsed", "format": "json", "total": total, "passed": passed, "failed": failed, "errors": errors, "skipped": skipped, "cases": (cases or [])[:100]}

    def _combine_report_summaries(self, summaries: list[dict[str, Any]], parse_errors: list[dict[str, str]]) -> dict[str, Any]:
        combined = {
            "parse_status": "failed" if parse_errors else ("parsed" if summaries else "skipped"),
            "total": sum(int(summary.get("total", 0)) for summary in summaries),
            "passed": sum(int(summary.get("passed", 0)) for summary in summaries),
            "failed": sum(int(summary.get("failed", 0)) for summary in summaries),
            "errors": sum(int(summary.get("errors", 0)) for summary in summaries),
            "skipped": sum(int(summary.get("skipped", 0)) for summary in summaries),
            "formats": sorted({str(summary.get("format", "")) for summary in summaries if summary.get("format")}),
            "parse_errors": parse_errors,
        }
        cases: list[dict[str, Any]] = []
        for summary in summaries:
            cases.extend(case for case in summary.get("cases", []) if isinstance(case, dict))
        combined["cases"] = cases[:100]
        return combined

    def _test_run_status_from_summary(self, summary: dict[str, Any]) -> str:
        if summary.get("parse_status") == "failed" or int(summary.get("failed", 0)) or int(summary.get("errors", 0)):
            return "failed"
        if summary.get("parse_status") == "parsed":
            return "passed"
        return "running"

    def _test_run_results_from_summary(self, summary: dict[str, Any]) -> list[dict[str, Any]]:
        results = summary.get("cases", [])
        return results if isinstance(results, list) else []

    def _upsert_ingest_quality_gate(self, actor_id: str, project_id: str, report: Report, summary: dict[str, Any]) -> QualityGate:
        status = "passed" if summary.get("parse_status") == "parsed" and not int(summary.get("failed", 0)) and not int(summary.get("errors", 0)) else "failed"
        gate = next((candidate for candidate in self.quality_gates.values() if candidate.project_id == project_id and candidate.name == "Automated Test Report Gate"), None)
        conditions = [
            {"metric": "parse_status", "equals": "parsed"},
            {"metric": "failed", "equals": 0},
            {"metric": "errors", "equals": 0},
        ]
        if gate is None:
            gate = QualityGate(project_id=project_id, name="Automated Test Report Gate", conditions=conditions, last_report_id=report.id, status=status)
            gate.validate()
            gate.id = self._id("qgt")
            stamp(gate)
            self.quality_gates[gate.id] = gate
            self._audit(actor_id, "quality_gate.created", "quality_gate", gate.id, {"project_id": project_id, "status": gate.status})
            return gate
        gate.conditions = conditions
        gate.last_report_id = report.id
        gate.status = status
        gate.updated_at = now_utc()
        self._audit(actor_id, "quality_gate.updated", "quality_gate", gate.id, {"project_id": project_id, "status": gate.status})
        return gate

    def _matches_file_filters(self, file_object: FileObject, filters: dict[str, str]) -> bool:
        allowed = {"owner_id", "resource_type", "resource_id", "module", "status"}
        unknown = set(filters) - allowed
        if unknown:
            raise InvalidInput("unsupported file filter")
        for key, expected in filters.items():
            if str(getattr(file_object, key)) != str(expected):
                return False
        return True

    def _file_audit_metadata(self, file_object: FileObject) -> dict[str, Any]:
        return {
            "owner_id": file_object.owner_id,
            "resource_type": file_object.resource_type,
            "resource_id": file_object.resource_id,
            "module": file_object.module,
            "size_bytes": file_object.size_bytes,
            "storage_provider": self.storage.provider,
        }

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


def highest_role(roles: list[dict[str, str]]) -> str:
    rank = {"Viewer": 1, "Operator": 2, "Admin": 3}
    selected = ""
    selected_rank = 0
    for role_entry in roles:
        role = normalize_role(role_entry.get("name"))
        if rank.get(role, 0) > selected_rank:
            selected = role
            selected_rank = rank[role]
    return selected


def stamp(entity: Any) -> None:
    value = now_utc()
    entity.created_at = value
    entity.updated_at = value


def pick(data: dict[str, Any], model: type[T]) -> dict[str, Any]:
    fields = set(model.__dataclass_fields__.keys())  # type: ignore[attr-defined]
    return {key: value for key, value in data.items() if key in fields}


def _is_past(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed <= datetime.now(timezone.utc)


class LocalSecretStore:
    def __init__(self) -> None:
        configured_key = os.environ.get("OPSPILOT_SECRET_FINGERPRINT_KEY")
        self._fingerprint_key = configured_key.encode("utf-8") if configured_key else secrets.token_bytes(32)
        self._vault: dict[str, str] = {}

    def put(self, secret: str) -> str:
        secret_ref = f"sec_{secrets.token_urlsafe(18)}"
        self._vault[secret_ref] = secret
        return secret_ref

    def rotate(self, secret_ref: str, secret: str) -> None:
        if secret_ref not in self._vault:
            raise NotFound("secret reference not found")
        self._vault[secret_ref] = secret

    def delete(self, secret_ref: str) -> None:
        self._vault.pop(secret_ref, None)

    def get(self, secret_ref: str) -> str:
        if secret_ref not in self._vault:
            raise NotFound("secret reference not found")
        return self._vault[secret_ref]

    def verify(self, secret_ref: str, candidate: str) -> bool:
        if secret_ref not in self._vault:
            raise NotFound("secret reference not found")
        return hmac.compare_digest(self._vault[secret_ref], candidate)

    def fingerprint(self, secret: str) -> str:
        digest = hmac.new(self._fingerprint_key, secret.encode("utf-8"), hashlib.sha256).hexdigest()
        return digest[:24]


def normalize_repositories(repositories: list[dict[str, str]], base_url: str) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for index, repository in enumerate(repositories, start=1):
        path = str(repository.get("path", "")).strip()
        if not path:
            raise InvalidInput("repositories require path")
        repo_id = str(repository.get("id", "") or path)
        raw_web_url = str(repository.get("web_url", "") or f"{base_url.rstrip('/')}/{path}")
        web_url = sanitize_public_url(raw_web_url, allow_path=True)
        name = str(repository.get("name", "") or path.rsplit("/", 1)[-1] or f"repository-{index}")
        normalized.append({"id": repo_id, "path": path, "name": name, "web_url": web_url})
    return normalized


def public_gitlab_branch(branch: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(branch.get("name", "")),
        "default": bool(branch.get("default", False)),
        "protected": bool(branch.get("protected", False)),
    }


def foundation_store_from_env() -> MemoryStore:
    dsn = os.environ.get("OPSPILOT_FOUNDATION_MYSQL_DSN", "").strip()
    if not dsn:
        return MemoryStore()
    from .mysql_store import MySQLStore

    return MySQLStore(dsn)
