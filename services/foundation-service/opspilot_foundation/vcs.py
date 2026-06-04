from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .domain import Conflict, InvalidInput, sanitize_public_url


class GitLabClient:
    def list_projects(self, base_url: str, token: str, search: str = "", page: int = 1, per_page: int = 20) -> list[dict[str, str]]:
        raise NotImplementedError

    def list_branches(self, base_url: str, token: str, repository_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    def create_branch(self, base_url: str, token: str, repository_id: str, branch: str, ref: str) -> dict[str, Any]:
        raise NotImplementedError

    def create_merge_request(self, base_url: str, token: str, repository_id: str, source_branch: str, target_branch: str, title: str) -> dict[str, Any]:
        raise NotImplementedError

    def get_merge_request(self, base_url: str, token: str, repository_id: str, merge_request_iid: str) -> dict[str, Any]:
        raise NotImplementedError


class LocalGitLabClient(GitLabClient):
    def __init__(self) -> None:
        self._branches: dict[str, list[dict[str, Any]]] = {}
        self._merge_requests: dict[tuple[str, str], dict[str, Any]] = {}

    def list_projects(self, base_url: str, token: str, search: str = "", page: int = 1, per_page: int = 20) -> list[dict[str, str]]:
        projects = [
            {"id": "stub-ops-platform", "path": "platform/opspilot", "name": "OpsPilot", "web_url": f"{base_url.rstrip('/')}/platform/opspilot"},
            {"id": "stub-infra", "path": "platform/infra", "name": "Infra", "web_url": f"{base_url.rstrip('/')}/platform/infra"},
        ]
        needle = search.lower().strip()
        if needle:
            projects = [project for project in projects if needle in project["path"].lower() or needle in project["name"].lower()]
        return projects

    def list_branches(self, base_url: str, token: str, repository_id: str) -> list[dict[str, Any]]:
        return [dict(branch) for branch in self._branches.setdefault(repository_id, [{"name": "main", "default": True, "protected": False}])]

    def create_branch(self, base_url: str, token: str, repository_id: str, branch: str, ref: str) -> dict[str, Any]:
        if not branch or not ref:
            raise InvalidInput("create branch requires branch and ref")
        branches = self._branches.setdefault(repository_id, [{"name": "main", "default": True, "protected": False}])
        if any(existing["name"] == branch for existing in branches):
            raise Conflict("branch already exists")
        created = {"name": branch, "default": False, "protected": False, "ref": ref}
        branches.append(created)
        return dict(created)

    def create_merge_request(self, base_url: str, token: str, repository_id: str, source_branch: str, target_branch: str, title: str) -> dict[str, Any]:
        if not source_branch or not target_branch or not title:
            raise InvalidInput("merge request requires source_branch, target_branch, and title")
        iid = str(len([key for key in self._merge_requests if key[0] == repository_id]) + 1)
        mr = {
            "iid": iid,
            "state": "opened",
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": title,
            "web_url": f"{base_url.rstrip('/')}/-/merge_requests/{iid}",
        }
        self._merge_requests[(repository_id, iid)] = mr
        return dict(mr)

    def get_merge_request(self, base_url: str, token: str, repository_id: str, merge_request_iid: str) -> dict[str, Any]:
        mr = self._merge_requests.get((repository_id, str(merge_request_iid)))
        if mr is None:
            raise InvalidInput("merge request not found")
        return dict(mr)


class GitLabAPIClient(GitLabClient):
    def list_projects(self, base_url: str, token: str, search: str = "", page: int = 1, per_page: int = 20) -> list[dict[str, str]]:
        query = {"membership": "true", "simple": "true", "page": str(page), "per_page": str(per_page)}
        if search:
            query["search"] = search
        projects = self._request(base_url, token, "GET", "/api/v4/projects", query=query)
        return [
            {
                "id": str(project["id"]),
                "path": str(project.get("path_with_namespace") or project.get("path") or project["id"]),
                "name": str(project.get("name") or project.get("path") or project["id"]),
                "web_url": sanitize_public_url(str(project.get("web_url", "")), allow_path=True),
            }
            for project in projects
        ]

    def list_branches(self, base_url: str, token: str, repository_id: str) -> list[dict[str, Any]]:
        branches = self._request(base_url, token, "GET", f"/api/v4/projects/{quote(repository_id, safe='')}/repository/branches")
        return [{"name": branch["name"], "default": bool(branch.get("default", False)), "protected": bool(branch.get("protected", False))} for branch in branches]

    def create_branch(self, base_url: str, token: str, repository_id: str, branch: str, ref: str) -> dict[str, Any]:
        response = self._request(
            base_url,
            token,
            "POST",
            f"/api/v4/projects/{quote(repository_id, safe='')}/repository/branches",
            body={"branch": branch, "ref": ref},
        )
        return self._public_branch(response)

    def create_merge_request(self, base_url: str, token: str, repository_id: str, source_branch: str, target_branch: str, title: str) -> dict[str, Any]:
        response = self._request(
            base_url,
            token,
            "POST",
            f"/api/v4/projects/{quote(repository_id, safe='')}/merge_requests",
            body={"source_branch": source_branch, "target_branch": target_branch, "title": title},
        )
        return self._public_merge_request(response)

    def get_merge_request(self, base_url: str, token: str, repository_id: str, merge_request_iid: str) -> dict[str, Any]:
        response = self._request(base_url, token, "GET", f"/api/v4/projects/{quote(repository_id, safe='')}/merge_requests/{quote(str(merge_request_iid), safe='')}")
        return self._public_merge_request(response)

    def _request(self, base_url: str, token: str, method: str, path: str, query: dict[str, str] | None = None, body: dict[str, Any] | None = None) -> Any:
        if not token:
            raise InvalidInput("gitlab credential secret is unavailable")
        url = f"{base_url.rstrip('/')}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(url, data=data, method=method, headers={"PRIVATE-TOKEN": token, "Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=10) as response:
                payload = response.read().decode("utf-8")
        except OSError as exc:
            raise InvalidInput("gitlab api request failed") from exc
        return json.loads(payload) if payload else {}

    def _public_merge_request(self, response: dict[str, Any]) -> dict[str, Any]:
        return {
            "iid": str(response.get("iid", "")),
            "state": str(response.get("state", "")),
            "source_branch": str(response.get("source_branch", "")),
            "target_branch": str(response.get("target_branch", "")),
            "title": str(response.get("title", "")),
            "web_url": sanitize_public_url(str(response.get("web_url", "")), allow_path=True) if response.get("web_url") else "",
        }

    def _public_branch(self, response: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": str(response.get("name", "")),
            "default": bool(response.get("default", False)),
            "protected": bool(response.get("protected", False)),
        }
