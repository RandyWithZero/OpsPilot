from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import asdict
from threading import RLock
from typing import Any, TypeVar

from .domain import (
    Agent,
    Asset,
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
    now_utc,
    redact_sensitive_payload,
    sanitize_public_url,
)
from .auth import PermissionDenied
from .vcs import GitLabAPIClient, GitLabClient, LocalGitLabClient

T = TypeVar("T")


class MemoryStore:
    def __init__(self, gitlab_client: GitLabClient | None = None) -> None:
        self._lock = RLock()
        self._ids = 0
        self.users: dict[str, User] = {}
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
        self.test_cases: dict[str, TestCase] = {}
        self.test_suites: dict[str, TestSuite] = {}
        self.test_runs: dict[str, TestRun] = {}
        self.reports: dict[str, Report] = {}
        self.quality_gates: dict[str, QualityGate] = {}
        self.secret_store = LocalSecretStore()
        self.gitlab_client = gitlab_client or (GitLabAPIClient() if os.environ.get("OPSPILOT_GITLAB_LIVE") == "1" else LocalGitLabClient())
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
            for environment_id in list(project.environment_ids):
                self.environments.pop(environment_id, None)
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
            asset.capabilities = unique(asset.capabilities)
            stamp(asset)
            self.assets[asset.id] = asset
            self._audit(actor_id, "asset.created", "asset", asset.id, {"category": asset.category})
            return asdict(asset)

    def list_assets(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(asset) for asset in self.assets.values()]

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
            for key in ("category", "name", "status", "owner_id", "location", "parent_id", "capabilities", "properties"):
                if key in data:
                    setattr(asset, key, data[key])
            asset.capabilities = unique(asset.capabilities)
            asset.validate()
            asset.updated_at = now_utc()
            self._audit(actor_id, "asset.updated", "asset", asset.id, {"status": asset.status})
            return asdict(asset)

    def delete_asset(self, actor_id: str, asset_id: str) -> dict[str, str]:
        with self._lock:
            asset = self.assets.pop(asset_id, None)
            if asset is None:
                raise NotFound("asset not found")
            for project in self.projects.values():
                project.asset_ids = [existing_id for existing_id in project.asset_ids if existing_id != asset_id]
                project.updated_at = now_utc()
            for environment in self.environments.values():
                environment.asset_ids = [existing_id for existing_id in environment.asset_ids if existing_id != asset_id]
                environment.updated_at = now_utc()
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

    def update_environment(self, actor_id: str, environment_id: str, data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            environment = self._environment(environment_id)
            if "project_id" in data and data["project_id"] not in self.projects:
                raise NotFound("project not found")
            if "owner_id" in data and data["owner_id"] and data["owner_id"] not in self.users:
                raise NotFound("owner not found")
            for asset_id in data.get("asset_ids", []):
                if asset_id not in self.assets:
                    raise NotFound("asset not found")
            old_project_id = environment.project_id
            for key in ("project_id", "name", "type", "status", "owner_id", "member_ids", "asset_ids", "endpoints"):
                if key in data:
                    setattr(environment, key, data[key])
            environment.member_ids = unique([*environment.member_ids, environment.owner_id])
            environment.asset_ids = unique(environment.asset_ids)
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
            self._audit(actor_id, "file.created", "file", file_object.id, {"filename": file_object.filename, "size_bytes": file_object.size_bytes})
            return self._public_file(file_object)

    def list_file_objects(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._public_file(file_object) for file_object in self.files.values()]

    def create_upload_grant(self, actor_id: str, file_id: str) -> dict[str, Any]:
        with self._lock:
            file_object = self._file(file_id)
            grant = {
                "file_id": file_object.id,
                "method": "PUT",
                "url": f"local://uploads/{file_object.storage_key}",
                "expires_in_seconds": 900,
            }
            self._audit(actor_id, "file.upload_grant.created", "file", file_object.id, {})
            return grant

    def create_upload_session(self, actor_id: str, file_id: str) -> dict[str, Any]:
        with self._lock:
            file_object = self._file(file_id)
            session = UploadSession(file_id=file_object.id, url=f"local://uploads/{file_object.storage_key}")
            session.validate()
            session.id = self._id("upl")
            stamp(session)
            self.upload_sessions[session.id] = session
            self._audit(actor_id, "file.upload_session.created", "file", file_object.id, {"upload_session_id": session.id})
            return asdict(session)

    def complete_upload_session(self, actor_id: str, session_id: str, data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            session = self._upload_session(session_id)
            if session.status != "open":
                raise Conflict("upload session is not open")
            file_object = self._file(session.file_id)
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

    def create_download_grant(self, actor_id: str, file_id: str) -> dict[str, Any]:
        with self._lock:
            file_object = self._file(file_id)
            grant = {
                "file_id": file_object.id,
                "method": "GET",
                "url": f"local://downloads/{file_object.storage_key}",
                "expires_in_seconds": 900,
            }
            self._audit(actor_id, "file.download_grant.created", "file", file_object.id, {})
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
            workflow = self.workflows.pop(workflow_id, None)
            if workflow is None:
                raise NotFound("workflow not found")
            for version_id, version in list(self.workflow_versions.items()):
                if version.workflow_id == workflow_id:
                    self.workflow_versions.pop(version_id, None)
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
                step.output = data["output"]
            if "error" in data:
                step.error = str(data["error"])
            step.updated_at = stamp_time
            self._audit(actor_id, "workflow.step.updated", "workflow_step_run", step.id, {"workflow_run_id": run.id, "step_type": step.step_type, "status": step.status})
            self._refresh_workflow_run_status(run)
            return self._workflow_run_response(run)

    def create_test_case(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        test_case = TestCase(**pick(data, TestCase))
        test_case.validate()
        with self._lock:
            self._project(test_case.project_id)
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
            self._project(suite.project_id)
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
            self._project(run.project_id)
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
            self._project(report.project_id)
            if report.test_run_id:
                run = self._test_run(report.test_run_id)
                if run.project_id != report.project_id:
                    raise Conflict("test run belongs to another project")
            report.file_ids = unique(report.file_ids)
            for file_id in report.file_ids:
                self._file(file_id)
            report.id = self._id("rpt")
            stamp(report)
            self.reports[report.id] = report
            self._audit(actor_id, "report.created", "report", report.id, {"project_id": report.project_id, "report_type": report.report_type})
            return asdict(report)

    def list_reports(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(report) for report in self.reports.values()]

    def create_quality_gate(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        gate = QualityGate(**pick(data, QualityGate))
        gate.validate()
        with self._lock:
            self._project(gate.project_id)
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
        if actor_id not in unique([project.owner_id, *project.member_ids]):
            raise PermissionDenied("actor is not a project member")
        for binding in project.repository_bindings:
            if binding.get("provider") == "gitlab" and binding.get("profile_id") == profile_id and binding.get("repository_id") == repository_id:
                return project
        raise Conflict("repository is not bound to project")

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

    def _validate_step_transition(self, step: WorkflowStepRun, next_status: str) -> None:
        if next_status not in {"running", "completed", "failed", "skipped"}:
            raise InvalidInput("unsupported workflow step status")
        if step.step_type == "manual" and next_status == "skipped":
            raise InvalidInput("manual workflow step runs cannot be skipped")
        allowed = {
            "pending": {"running", "completed", "failed", "skipped"},
            "running": {"completed", "failed", "skipped"},
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
