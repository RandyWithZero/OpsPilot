import base64
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from opspilot_foundation.store import MemoryStore  # noqa: E402
from opspilot_foundation.mysql_store import MySQLStore  # noqa: E402
from opspilot_foundation.server import FoundationHandler  # noqa: E402
from opspilot_foundation.storage import LocalFileStorage, S3CompatibleStorage  # noqa: E402
from opspilot_foundation.domain import InvalidInput  # noqa: E402
from opspilot_foundation.auth import (  # noqa: E402
    ActorContext,
    PermissionDenied,
    actor_from_headers,
    permission_for_request,
    require_permission,
)


class FakeGitLabClient:
    def __init__(self) -> None:
        self.projects = [
            {"id": "100", "path": "platform/opspilot", "name": "OpsPilot", "web_url": "https://gitlab.example.com/platform/opspilot"},
            {"id": "200", "path": "platform/infra", "name": "Infra", "web_url": "https://gitlab.example.com/platform/infra"},
            {"id": "300", "path": "apps/console", "name": "Console", "web_url": "https://gitlab.example.com/apps/console"},
        ]
        self.branches = {"100": [{"name": "main", "default": True, "protected": False}]}
        self.merge_requests = {}
        self.fail_next_merge_request = False

    def list_projects(self, base_url, token, search="", page=1, per_page=20):
        return [project for project in self.projects if not search or search.lower() in project["path"].lower() or search.lower() in project["name"].lower()]

    def list_branches(self, base_url, token, repository_id):
        return [dict(branch) for branch in self.branches.get(repository_id, [])]

    def create_branch(self, base_url, token, repository_id, branch, ref):
        created = {"name": branch, "default": False, "protected": False, "ref": ref}
        self.branches.setdefault(repository_id, []).append(created)
        return dict(created)

    def create_merge_request(self, base_url, token, repository_id, source_branch, target_branch, title):
        if self.fail_next_merge_request:
            self.fail_next_merge_request = False
            raise InvalidInput("gitlab rejected merge request")
        iid = str(len(self.merge_requests) + 1)
        merge_request = {
            "iid": iid,
            "state": "opened",
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": title,
            "web_url": f"{base_url}/platform/opspilot/-/merge_requests/{iid}",
        }
        self.merge_requests[(repository_id, iid)] = merge_request
        return dict(merge_request)

    def get_merge_request(self, base_url, token, repository_id, merge_request_iid):
        return dict(self.merge_requests[(repository_id, str(merge_request_iid))])


class FakeMySQLDatabase:
    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, object]]] = {}
        self.commits = 0

    def connect(self):
        return FakeMySQLConnection(self)


class FakeMySQLConnection:
    def __init__(self, database: FakeMySQLDatabase) -> None:
        self.database = database

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return FakeMySQLCursor(self.database)

    def commit(self) -> None:
        self.database.commits += 1


class FakeMySQLCursor:
    def __init__(self, database: FakeMySQLDatabase) -> None:
        self.database = database
        self.rows: list[dict[str, object]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        normalized = " ".join(sql.strip().split())
        upper = normalized.upper()
        if upper.startswith("CREATE TABLE"):
            return
        if upper.startswith("SELECT VERSION FROM FOUNDATION_SCHEMA_MIGRATIONS"):
            self.rows = [{"version": row["version"]} for row in self.database.tables.get("foundation_schema_migrations", [])]
            return
        if upper.startswith("SELECT 1"):
            self.rows = [{"1": 1}]
            return
        if upper.startswith("SELECT SECRET_REF, SECRET_VALUE FROM SECRET_REFS"):
            self.rows = list(self.database.tables.get("secret_refs", []))
            return
        if upper.startswith("SELECT PAYLOAD FROM "):
            table = normalized.split(" FROM ", 1)[1].split(" ", 1)[0]
            self.rows = list(self.database.tables.get(table, []))
            return
        if upper.startswith("DELETE FROM "):
            table = normalized.split(" ", 2)[2]
            self.database.tables[table] = []
            return
        if upper.startswith("INSERT INTO "):
            table = normalized.split(" ", 3)[2]
            columns_text = normalized.split("(", 1)[1].split(")", 1)[0]
            columns = [column.strip() for column in columns_text.split(",")]
            self.database.tables.setdefault(table, []).append(dict(zip(columns, params)))
            return
        raise AssertionError(f"unexpected SQL: {sql}")

    def fetchall(self):
        return list(self.rows)


class FoundationSliceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.storage_dir = tempfile.TemporaryDirectory()
        self.store = MemoryStore(storage=LocalFileStorage(self.storage_dir.name))

    def tearDown(self) -> None:
        self.storage_dir.cleanup()

    def test_create_and_link_inventory_slice(self) -> None:
        user = self.store.create_user(
            "usr_test_actor",
            {"email": "admin@example.com", "name": "Admin", "roles": [{"scope": "platform", "name": "Admin"}]},
        )
        self.assertTrue(user["id"].startswith("usr_"))
        self.assertEqual(user["status"], "active")

        project = self.store.create_project(
            "usr_test_actor",
            {"key": "OPS", "name": "Ops Platform", "owner_id": user["id"]},
        )
        self.assertEqual(project["member_ids"], [user["id"]])

        asset = self.store.create_asset(
            "usr_test_actor",
            {"category": "workstation", "name": "ws-01", "owner_id": user["id"], "capabilities": ["gpu", "linux", "gpu"], "tags": ["cuda", "cuda"]},
        )
        self.assertEqual(asset["capabilities"], ["gpu", "linux"])
        self.assertEqual(asset["tags"], ["cuda"])
        self.store.link_project_asset("usr_test_actor", project["id"], asset["id"])

        environment = self.store.create_environment(
            "usr_test_actor",
            {
                "project_id": project["id"],
                "name": "QA Lab",
                "type": "QA",
                "owner_id": user["id"],
                "asset_ids": [asset["id"]],
                "endpoints": [{"name": "ssh", "url": "ssh://qa-lab"}],
            },
        )
        self.assertEqual(environment["project_id"], project["id"])

        linked = self.store.link_project_asset("usr_test_actor", project["id"], asset["id"])
        self.assertEqual(linked["asset_ids"], [asset["id"]])

        events = self.store.list_audit_events()
        self.assertGreaterEqual(len(events), 5)
        self.assertEqual(events[0]["action"], "project.asset.linked")

    def test_duplicate_user_email_conflicts(self) -> None:
        self.store.create_user("usr_test_actor", {"email": "admin@example.com", "name": "Admin"})
        with self.assertRaises(Exception) as raised:
            self.store.create_user("usr_test_actor", {"email": "admin@example.com", "name": "Admin 2"})
        self.assertEqual(getattr(raised.exception, "code", ""), "conflict")

    def test_update_unlink_and_delete_inventory_slice(self) -> None:
        user = self.store.create_user("usr_test_actor", {"email": "admin@example.com", "name": "Admin"})
        project = self.store.create_project("usr_test_actor", {"key": "OPS", "name": "Ops Platform", "owner_id": user["id"]})
        asset = self.store.create_asset("usr_test_actor", {"category": "vm", "name": "runner-01"})
        self.store.link_project_asset("usr_test_actor", project["id"], asset["id"])
        environment = self.store.create_environment(
            "usr_test_actor",
            {"project_id": project["id"], "name": "DEV", "type": "DEV", "owner_id": user["id"], "asset_ids": [asset["id"]]},
        )

        updated_user = self.store.update_user("usr_test_actor", user["id"], {"status": "inactive"})
        self.assertEqual(updated_user["status"], "inactive")

        linked = self.store.link_project_asset("usr_test_actor", project["id"], asset["id"])
        self.assertEqual(linked["asset_ids"], [asset["id"]])
        unlinked = self.store.unlink_project_asset("usr_test_actor", project["id"], asset["id"])
        self.assertEqual(unlinked["asset_ids"], [])

        updated_environment = self.store.update_environment(
            "usr_test_actor",
            environment["id"],
            {"name": "DEV Primary", "type": "DEV", "project_id": project["id"], "owner_id": user["id"], "asset_ids": []},
        )
        self.assertEqual(updated_environment["name"], "DEV Primary")

        self.store.delete_environment("usr_test_actor", environment["id"])
        self.assertEqual(self.store.list_environments(), [])

    def test_asset_hierarchy_rejects_cycles_and_supports_filters(self) -> None:
        owner = self.store.create_user("usr_test_actor", {"email": "owner@example.com", "name": "Owner"})
        project = self.store.create_project("usr_test_actor", {"key": "OPS", "name": "Ops", "owner_id": owner["id"]})
        workstation = self.store.create_asset(
            "usr_test_actor",
            {"category": "workstation", "name": "ws-01", "capabilities": ["linux", "cuda"], "tags": ["qe-lab"]},
        )
        gpu = self.store.create_asset(
            "usr_test_actor",
            {"category": "gpu", "name": "rtx-01", "parent_id": workstation["id"], "capabilities": ["cuda"]},
        )
        self.store.link_project_asset("usr_test_actor", project["id"], workstation["id"])
        self.store.link_project_asset("usr_test_actor", project["id"], gpu["id"])

        with self.assertRaises(Exception) as raised:
            self.store.update_asset("usr_test_actor", workstation["id"], {"parent_id": gpu["id"]})

        self.assertEqual(getattr(raised.exception, "code", ""), "conflict")
        self.assertEqual([asset["id"] for asset in self.store.list_assets({"category": "gpu"})], [gpu["id"]])
        self.assertEqual([asset["id"] for asset in self.store.list_assets({"capability": "cuda", "project_id": project["id"]})], [workstation["id"], gpu["id"]])

    def test_environment_bindings_validate_project_members_assets_and_files(self) -> None:
        owner = self.store.create_user("usr_test_actor", {"email": "owner@example.com", "name": "Owner"})
        member = self.store.create_user("usr_test_actor", {"email": "member@example.com", "name": "Member"})
        outsider = self.store.create_user("usr_test_actor", {"email": "outsider@example.com", "name": "Outsider"})
        project = self.store.create_project(
            "usr_test_actor",
            {"key": "OPS", "name": "Ops", "owner_id": owner["id"], "member_ids": [member["id"]]},
        )
        other_project = self.store.create_project("usr_test_actor", {"key": "OTH", "name": "Other", "owner_id": outsider["id"]})
        project_asset = self.store.create_asset("usr_test_actor", {"category": "server", "name": "srv-01"})
        other_asset = self.store.create_asset("usr_test_actor", {"category": "server", "name": "srv-02"})
        self.store.link_project_asset("usr_test_actor", project["id"], project_asset["id"])
        self.store.link_project_asset("usr_test_actor", other_project["id"], other_asset["id"])

        with self.assertRaises(Exception) as asset_error:
            self.store.create_environment(
                "usr_test_actor",
                {"project_id": project["id"], "name": "QA", "type": "QA", "owner_id": owner["id"], "asset_ids": [other_asset["id"]]},
            )
        self.assertEqual(getattr(asset_error.exception, "code", ""), "conflict")

        with self.assertRaises(Exception) as member_error:
            self.store.create_environment(
                "usr_test_actor",
                {"project_id": project["id"], "name": "QE", "type": "QE", "owner_id": owner["id"], "member_ids": [outsider["id"]]},
            )
        self.assertEqual(getattr(member_error.exception, "code", ""), "conflict")

        environment = self.store.create_environment(
            "usr_test_actor",
            {"project_id": project["id"], "name": "QA", "type": "QA", "owner_id": owner["id"]},
        )
        linked_asset = self.store.link_environment_asset("usr_test_actor", environment["id"], project_asset["id"])
        linked_member = self.store.link_environment_member("usr_test_actor", environment["id"], member["id"])
        file_object = self.store.create_file_object(
            "usr_test_actor",
            {
                "filename": "qa-plan.txt",
                "content_type": "text/plain",
                "size_bytes": 42,
                "owner_id": owner["id"],
                "resource_type": "environment",
                "resource_id": environment["id"],
                "module": "attachments",
            },
        )
        linked_file = self.store.link_environment_file(owner["id"], environment["id"], file_object["id"])

        self.assertEqual(linked_asset["asset_ids"], [project_asset["id"]])
        self.assertEqual(linked_member["member_ids"], [owner["id"], member["id"]])
        self.assertEqual(linked_file["file_ids"], [file_object["id"]])
        self.assertEqual([env["id"] for env in self.store.list_environments({"project_id": project["id"], "asset_id": project_asset["id"]})], [environment["id"]])

        self.store.delete_file_object("usr_test_actor", file_object["id"])
        self.assertEqual(self.store.list_environments()[0]["file_ids"], [])
        self.store.delete_asset("usr_test_actor", project_asset["id"])
        self.assertEqual(self.store.list_projects()[0]["asset_ids"], [])
        self.assertEqual(self.store.list_environments()[0]["asset_ids"], [])
        actions = [event["action"] for event in self.store.list_audit_events()]
        self.assertIn("environment.asset.linked", actions)
        self.assertIn("environment.member.linked", actions)
        self.assertIn("environment.file.linked", actions)

    def test_environment_file_binding_claims_owned_files_and_rejects_unauthorized_refs(self) -> None:
        owner = self.store.create_user("usr_test_actor", {"email": "owner@example.com", "name": "Owner"})
        member = self.store.create_user("usr_test_actor", {"email": "member@example.com", "name": "Member"})
        outsider = self.store.create_user("usr_test_actor", {"email": "outsider@example.com", "name": "Outsider"})
        project = self.store.create_project(
            "usr_test_actor",
            {"key": "OPS", "name": "Ops", "owner_id": owner["id"], "member_ids": [member["id"]]},
        )
        environment = self.store.create_environment(
            "usr_test_actor",
            {"project_id": project["id"], "name": "QA", "type": "QA", "owner_id": owner["id"]},
        )
        owned_unbound = self.store.create_file_object(
            owner["id"],
            {"filename": "owned.txt", "content_type": "text/plain", "size_bytes": 1, "owner_id": owner["id"]},
        )
        claimed = self.store.link_environment_file(owner["id"], environment["id"], owned_unbound["id"])
        claimed_file = self.store.list_file_objects({"owner_id": owner["id"]})[0]

        self.assertEqual(claimed["file_ids"], [owned_unbound["id"]])
        self.assertEqual(claimed_file["resource_type"], "environment")
        self.assertEqual(claimed_file["resource_id"], environment["id"])

        cross_owner = self.store.create_file_object(
            outsider["id"],
            {"filename": "outside.txt", "content_type": "text/plain", "size_bytes": 1, "owner_id": outsider["id"]},
        )
        with self.assertRaises(Exception) as owner_error:
            self.store.link_environment_file(owner["id"], environment["id"], cross_owner["id"])
        self.assertEqual(getattr(owner_error.exception, "code", ""), "permission_denied")

        wrong_resource = self.store.create_file_object(
            owner["id"],
            {
                "filename": "wrong.txt",
                "content_type": "text/plain",
                "size_bytes": 1,
                "owner_id": owner["id"],
                "resource_type": "asset",
                "resource_id": "ast_other",
            },
        )
        with self.assertRaises(Exception) as resource_error:
            self.store.link_environment_file(owner["id"], environment["id"], wrong_resource["id"])
        self.assertEqual(getattr(resource_error.exception, "code", ""), "conflict")

        listed = self.store.list_environments({"project_id": project["id"]})[0]
        self.assertEqual(listed["file_ids"], [owned_unbound["id"]])
        self.assertNotIn(cross_owner["id"], listed["file_ids"])
        self.assertNotIn(wrong_resource["id"], listed["file_ids"])
        actions = [event["action"] for event in self.store.list_audit_events()]
        self.assertIn("environment.file.claimed", actions)

    def test_environment_binding_missing_refs_do_not_half_write(self) -> None:
        owner = self.store.create_user("usr_test_actor", {"email": "owner@example.com", "name": "Owner"})
        project = self.store.create_project("usr_test_actor", {"key": "OPS", "name": "Ops", "owner_id": owner["id"]})
        environment = self.store.create_environment(
            "usr_test_actor",
            {"project_id": project["id"], "name": "QA", "type": "QA", "owner_id": owner["id"]},
        )

        with self.assertRaises(Exception) as member_error:
            self.store.link_environment_member("usr_test_actor", environment["id"], "usr_missing")
        with self.assertRaises(Exception) as asset_error:
            self.store.link_environment_asset("usr_test_actor", environment["id"], "ast_missing")

        self.assertEqual(getattr(member_error.exception, "code", ""), "not_found")
        self.assertEqual(getattr(asset_error.exception, "code", ""), "not_found")
        unchanged = self.store.list_environments()[0]
        self.assertEqual(unchanged["member_ids"], [owner["id"]])
        self.assertEqual(unchanged["asset_ids"], [])

    def test_archiving_or_retiring_assets_cleans_project_environment_refs_and_audits(self) -> None:
        owner = self.store.create_user("usr_test_actor", {"email": "owner@example.com", "name": "Owner"})
        project = self.store.create_project("usr_test_actor", {"key": "OPS", "name": "Ops", "owner_id": owner["id"]})
        retired = self.store.create_asset("usr_test_actor", {"category": "server", "name": "retire-me"})
        archived = self.store.create_asset("usr_test_actor", {"category": "server", "name": "archive-me"})
        deleted = self.store.create_asset("usr_test_actor", {"category": "server", "name": "delete-me"})
        for asset in (retired, archived, deleted):
            self.store.link_project_asset("usr_test_actor", project["id"], asset["id"])
        environment = self.store.create_environment(
            "usr_test_actor",
            {
                "project_id": project["id"],
                "name": "QA",
                "type": "QA",
                "owner_id": owner["id"],
                "asset_ids": [retired["id"], archived["id"], deleted["id"]],
            },
        )

        self.store.update_asset("usr_test_actor", retired["id"], {"status": "retired"})
        self.store.update_asset("usr_test_actor", archived["id"], {"status": "archived"})
        self.store.update_asset("usr_test_actor", deleted["id"], {"status": "deleted"})

        self.assertEqual(self.store.list_projects()[0]["asset_ids"], [])
        self.assertEqual(self.store.list_environments({"asset_id": retired["id"]}), [])
        self.assertEqual(self.store.list_environments()[0]["id"], environment["id"])
        self.assertEqual(self.store.list_environments()[0]["asset_ids"], [])
        asset_updates = [event for event in self.store.list_audit_events() if event["action"] == "asset.updated"]
        self.assertGreaterEqual(len(asset_updates), 3)

    def test_json_contract_uses_snake_case(self) -> None:
        user = self.store.create_user("usr_test_actor", {"email": "admin@example.com", "name": "Admin"})
        encoded = json.dumps(user)
        self.assertIn("created_at", encoded)
        self.assertNotIn("createdAt", encoded)

    def test_cors_headers_allow_web_console_development(self) -> None:
        headers = []

        class HandlerDouble:
            def send_header(self, key: str, value: str) -> None:
                headers.append((key, value))

        FoundationHandler._cors_headers(HandlerDouble())  # type: ignore[arg-type]

        self.assertIn(("Access-Control-Allow-Origin", "*"), headers)
        self.assertIn(("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS"), headers)
        self.assertIn(("Access-Control-Allow-Headers", "Content-Type,X-Actor-ID,X-Actor-Role,X-Gitlab-Token"), headers)

    def test_local_rbac_permission_matrix_for_high_risk_apis(self) -> None:
        self.assertEqual(actor_from_headers({}).role, "Viewer")
        self.assertEqual(actor_from_headers({"X-Actor-ID": "usr_operator", "X-Actor-Role": "operator"}).actor_id, "usr_operator")
        self.assertEqual(actor_from_headers({"X-Actor-Role": "viewer"}).role, "Viewer")
        self.assertEqual(actor_from_headers({"X-Actor-Role": "root"}).role, "")

        self.assert_missing_role_denied("GET", "/v1/credentials")
        self.assert_missing_role_denied("POST", "/v1/credentials")
        self.assert_missing_role_denied("POST", "/v1/files/fil_1/upload-grants")
        self.assert_missing_role_denied("PATCH", "/v1/workflow-runs/wfr_1/steps/wfs_1", {"status": "completed"})
        self.assert_missing_role_denied("DELETE", "/v1/projects/prj_1")
        self.assert_invalid_role_denied("GET", "/v1/projects")
        self.assert_invalid_role_denied("POST", "/v1/credentials")

        self.assert_allowed("Viewer", "GET", "/v1/projects")
        self.assert_denied("Viewer", "GET", "/v1/credentials")
        self.assert_denied("Viewer", "POST", "/v1/files/fil_1/upload-grants")
        self.assert_denied("Viewer", "PATCH", "/v1/workflow-runs/wfr_1/steps/wfs_1")
        self.assert_denied("Viewer", "DELETE", "/v1/projects/prj_1")

        self.assert_allowed("Operator", "POST", "/v1/files/fil_1/upload-grants")
        self.assert_allowed("Operator", "POST", "/v1/vcs/operations")
        self.assert_allowed("Operator", "POST", "/v1/workflows/wfl_1/runs")
        self.assert_allowed("Operator", "POST", "/v1/workflow-runs/wfr_1/start")
        self.assert_allowed("Operator", "PATCH", "/v1/workflow-runs/wfr_1/steps/wfs_1", {"status": "completed"})
        self.assert_allowed("Operator", "PATCH", "/v1/workflows/wfl_1/versions/wfv_1", {"status": "published"})
        self.assert_denied("Operator", "POST", "/v1/credentials")
        self.assert_denied("Operator", "POST", "/v1/users")
        self.assert_denied("Operator", "PATCH", "/v1/credentials/cred_1")
        self.assert_denied("Operator", "PATCH", "/v1/gitlab/profiles/glp_1")
        self.assert_denied("Operator", "PATCH", "/v1/users/usr_1")
        self.assert_denied("Operator", "PATCH", "/v1/agents/agt_1")
        self.assert_denied("Operator", "PATCH", "/v1/skills/skl_1")
        self.assert_denied("Operator", "PATCH", "/v1/projects/prj_1", {"status": "archived"})
        self.assert_denied("Operator", "DELETE", "/v1/projects/prj_1")

        self.assert_allowed("Admin", "GET", "/v1/credentials")
        self.assert_allowed("Admin", "POST", "/v1/credentials")
        self.assert_allowed("Admin", "PATCH", "/v1/gitlab/profiles/glp_1")
        self.assert_allowed("Admin", "DELETE", "/v1/projects/prj_1")

    def assert_allowed(self, role: str, method: str, path: str, body: dict | None = None) -> None:
        require_permission(ActorContext(actor_id="usr_test_actor", role=role), permission_for_request(method, path, body))

    def assert_denied(self, role: str, method: str, path: str, body: dict | None = None) -> None:
        with self.assertRaises(PermissionDenied):
            require_permission(ActorContext(actor_id="usr_test_actor", role=role), permission_for_request(method, path, body))

    def assert_missing_role_denied(self, method: str, path: str, body: dict | None = None) -> None:
        actor = actor_from_headers({})
        self.assert_denied(actor.role, method, path, body)

    def assert_invalid_role_denied(self, method: str, path: str, body: dict | None = None) -> None:
        actor = actor_from_headers({"X-Actor-Role": "root"})
        self.assert_denied(actor.role, method, path, body)

    def test_file_grants_are_metadata_only(self) -> None:
        file_object = self.store.create_file_object(
            "usr_test_actor",
            {"filename": "report.txt", "content_type": "text/plain", "size_bytes": 1024, "owner_id": "usr_external"},
        )

        upload = self.store.create_upload_grant("usr_test_actor", file_object["id"])
        download = self.store.create_download_grant("usr_test_actor", file_object["id"])

        self.assertEqual(upload["method"], "PUT")
        self.assertEqual(download["method"], "GET")
        self.assertNotIn("storage_key", file_object)
        self.assertTrue(upload["url"].startswith("opspilot://file-capabilities/upload/"))
        self.assertTrue(download["url"].startswith("opspilot://file-capabilities/download/"))
        self.assertNotIn("objects/", upload["url"])


class MySQLStorePersistenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.storage_dir = tempfile.TemporaryDirectory()
        self.database = FakeMySQLDatabase()
        self.gitlab_client = FakeGitLabClient()
        self.store = MySQLStore(
            "mysql://opspilot:opspilot@127.0.0.1:3306/opspilot_foundation",
            storage=LocalFileStorage(self.storage_dir.name),
            gitlab_client=self.gitlab_client,
            connection_factory=self.database.connect,
        )

    def tearDown(self) -> None:
        self.storage_dir.cleanup()

    def reload_store(self) -> MySQLStore:
        return MySQLStore(
            "mysql://opspilot:opspilot@127.0.0.1:3306/opspilot_foundation",
            storage=LocalFileStorage(self.storage_dir.name),
            gitlab_client=self.gitlab_client,
            connection_factory=self.database.connect,
        )

    def create_owned_project(self) -> tuple[dict, dict]:
        user = self.store.create_user("usr_test_actor", {"email": "owner@example.com", "name": "Owner"})
        project = self.store.create_project("usr_test_actor", {"key": "OPS", "name": "Ops", "owner_id": user["id"]})
        return user, project

    def create_workflow_with_run(self, project_id: str = "") -> tuple[dict, dict]:
        workflow = self.store.create_workflow("usr_test_actor", {"name": f"Deploy {project_id}", "project_id": project_id})
        self.store.create_workflow_version(
            "usr_test_actor",
            workflow["id"],
            {
                "version": "1",
                "nodes": [
                    {"id": "trigger", "type": "trigger", "name": "Start"},
                    {"id": "manual", "type": "manual", "name": "Approve"},
                    {"id": "result", "type": "result", "name": "Finish"},
                ],
                "edges": [
                    {"from_node_id": "trigger", "to_node_id": "manual"},
                    {"from_node_id": "manual", "to_node_id": "result"},
                ],
            },
        )
        run = self.store.create_workflow_run("usr_test_actor", workflow["id"], {})
        return workflow, run

    def test_create_update_delete_round_trips_through_mysql_snapshot(self) -> None:
        user = self.store.create_user("usr_test_actor", {"email": "owner@example.com", "name": "Owner"})
        updated = self.store.update_user("usr_test_actor", user["id"], {"name": "Updated Owner"})

        reloaded = self.reload_store()
        self.assertEqual(reloaded.list_users()[0]["name"], updated["name"])

        reloaded.delete_user("usr_test_actor", user["id"])
        self.assertEqual(self.reload_store().list_users(), [])

    def test_cross_table_references_still_validate_before_persist(self) -> None:
        with self.assertRaises(Exception) as raised:
            self.store.create_project("usr_test_actor", {"key": "OPS", "name": "Ops", "owner_id": "usr_missing"})

        self.assertEqual(getattr(raised.exception, "code", ""), "not_found")
        self.assertEqual(self.database.tables.get("projects", []), [])

    def test_workflow_run_predecessor_snapshot_survives_reload(self) -> None:
        _, project = self.create_owned_project()
        workflow, run = self.create_workflow_with_run(project["id"])
        reloaded_run = self.reload_store().list_workflow_runs(workflow["id"])[0]
        steps_by_node = {step["node_id"]: step for step in reloaded_run["steps"]}

        self.assertEqual(run["id"], reloaded_run["id"])
        self.assertEqual(steps_by_node["manual"]["predecessor_node_ids"], ["trigger"])
        self.assertEqual(steps_by_node["result"]["predecessor_node_ids"], ["manual"])

    def test_failed_gitlab_merge_request_operation_survives_reload(self) -> None:
        user, project = self.create_owned_project()
        credential = self.store.create_credential(user["id"], {"provider": "gitlab", "name": "GitLab", "secret": "glpat-secret"})
        profile = self.store.create_gitlab_profile(user["id"], {"name": "Primary GitLab", "base_url": "https://gitlab.example.com", "credential_ref_id": credential["id"]})
        self.store.sync_gitlab_repositories(user["id"], profile["id"], search="platform")
        self.store.link_project_repository(user["id"], project["id"], {"provider": "gitlab", "profile_id": profile["id"], "repository_id": "100"})
        self.gitlab_client.fail_next_merge_request = True

        with self.assertRaises(Exception) as raised:
            self.store.create_gitlab_merge_request(
                user["id"],
                profile["id"],
                "100",
                {"project_id": project["id"], "source_branch": "feature/fail", "target_branch": "main", "title": "Failing MR"},
            )

        self.assertEqual(getattr(raised.exception, "code", ""), "invalid_input")
        reloaded = self.reload_store()
        operations = reloaded.list_vcs_operations()
        audit_actions = [event["action"] for event in reloaded.list_audit_events()]

        self.assertEqual(len(operations), 1)
        self.assertEqual(operations[0]["status"], "failed")
        self.assertEqual(operations[0]["operation_type"], "open_merge_request")
        self.assertEqual(operations[0]["result"], {"error": "invalid_input"})
        self.assertIn("gitlab.merge_request.failed", audit_actions)

    def test_project_delete_cascades_mysql_child_rows_before_reload(self) -> None:
        user, project = self.create_owned_project()
        asset = self.store.create_asset("usr_test_actor", {"category": "vm", "name": "runner"})
        self.store.link_project_asset("usr_test_actor", project["id"], asset["id"])
        self.store.create_environment("usr_test_actor", {"project_id": project["id"], "name": "QA", "type": "QA", "owner_id": user["id"], "asset_ids": [asset["id"]]})
        self.create_workflow_with_run(project["id"])
        case = self.store.create_test_case("usr_test_actor", {"project_id": project["id"], "name": "Smoke"})
        suite = self.store.create_test_suite("usr_test_actor", {"project_id": project["id"], "name": "Release", "case_ids": [case["id"]]})
        test_run = self.store.create_test_run("usr_test_actor", {"project_id": project["id"], "suite_id": suite["id"]})
        file_object = self.store.upload_file_object(
            user["id"],
            {
                "owner_id": user["id"],
                "resource_type": "test_run",
                "resource_id": test_run["id"],
                "module": "reports",
                "filename": "report.txt",
                "content_type": "text/plain",
                "content_base64": base64.b64encode(b"ok").decode("ascii"),
            },
        )
        report = self.store.create_report(user["id"], {"project_id": project["id"], "title": "Report", "test_run_id": test_run["id"], "file_ids": [file_object["id"]]})
        self.store.create_quality_gate("usr_test_actor", {"project_id": project["id"], "name": "Gate", "last_report_id": report["id"]})

        self.store.delete_project("usr_test_actor", project["id"])
        reloaded = self.reload_store()

        self.assertEqual(reloaded.list_projects(), [])
        self.assertEqual(reloaded.list_environments(), [])
        self.assertEqual(reloaded.list_workflows(), [])
        self.assertEqual(reloaded.list_workflow_runs(), [])
        self.assertEqual(reloaded.list_test_cases(), [])
        self.assertEqual(reloaded.list_test_suites(), [])
        self.assertEqual(reloaded.list_test_runs(), [])
        self.assertEqual(reloaded.list_reports(), [])
        self.assertEqual(reloaded.list_quality_gates(), [])
        self.assertTrue(any(event["action"] == "project.deleted" for event in reloaded.list_audit_events()))

    def test_workflow_delete_cascades_versions_runs_and_steps_before_reload(self) -> None:
        _, project = self.create_owned_project()
        workflow, _ = self.create_workflow_with_run(project["id"])

        self.store.delete_workflow("usr_test_actor", workflow["id"])
        reloaded = self.reload_store()

        self.assertEqual(reloaded.list_workflows(), [])
        self.assertEqual(reloaded.workflow_versions, {})
        self.assertEqual(reloaded.list_workflow_runs(), [])
        self.assertEqual(reloaded.workflow_step_runs, {})
        self.assertTrue(any(event["action"] == "workflow.deleted" for event in reloaded.list_audit_events()))

    def test_file_grants_credentials_and_audit_events_are_persisted_safely(self) -> None:
        file_object = self.store.create_file_object(
            "usr_test_actor",
            {"filename": "report.txt", "content_type": "text/plain", "size_bytes": 10, "owner_id": "usr_test_actor"},
        )
        upload = self.store.create_upload_grant("usr_test_actor", file_object["id"])
        download = self.store.create_download_grant("usr_test_actor", file_object["id"])
        credential = self.store.create_credential("usr_test_actor", {"provider": "gitlab", "name": "GitLab", "secret": "super-secret"})

        self.assertNotIn("secret", credential)
        self.assertEqual(upload["method"], "PUT")
        self.assertEqual(download["method"], "GET")
        self.assertIn("storage_key", json.loads(self.database.tables["files"][0]["payload"]))
        self.assertNotIn("storage_key", file_object)
        self.assertEqual(self.database.tables["secret_refs"][0]["secret_value"], "super-secret")

        audit_payloads = [json.loads(row["payload"]) for row in self.database.tables["audit_events"]]
        self.assertTrue(any(event["action"] == "credential.created" for event in audit_payloads))
        self.assertFalse(any("super-secret" in json.dumps(event) for event in audit_payloads))
        self.assertNotIn("objects/", download["url"])
        self.assertNotIn("report.txt", upload["url"])
        self.assertNotIn("report.txt", download["url"])

    def test_file_upload_session_completion_marks_file_available(self) -> None:
        file_object = self.store.create_file_object(
            "usr_test_actor",
            {"filename": "run.log", "content_type": "text/plain", "size_bytes": 0, "owner_id": "usr_external"},
        )

        session = self.store.create_upload_session("usr_test_actor", file_object["id"])
        completed = self.store.complete_upload_session(
            "usr_test_actor",
            session["id"],
            {"checksum": "sha256:abc123", "size_bytes": 64},
        )
        download = self.store.create_download_grant("usr_test_actor", file_object["id"])

        self.assertEqual(session["status"], "open")
        self.assertEqual(completed["upload_session"]["status"], "completed")
        self.assertEqual(completed["file"]["status"], "available")
        self.assertEqual(completed["file"]["checksum"], "sha256:abc123")
        self.assertEqual(completed["file"]["size_bytes"], 64)
        self.assertEqual(download["method"], "GET")

        with self.assertRaises(Exception) as raised:
            self.store.complete_upload_session("usr_test_actor", session["id"], {})
        self.assertEqual(getattr(raised.exception, "code", ""), "conflict")

    def test_file_storage_key_is_server_generated_and_filename_is_sanitized(self) -> None:
        file_object = self.store.create_file_object(
            "usr_test_actor",
            {"filename": "safe-name.txt", "content_type": "text/plain", "size_bytes": 1, "storage_key": "../../secrets.txt"},
        )
        download = self.store.create_download_grant("usr_test_actor", file_object["id"])

        self.assertNotIn("storage_key", file_object)
        self.assertNotIn("../../secrets.txt", json.dumps({"file": file_object, "grant": download, "files": self.store.list_file_objects()}))
        self.assertNotIn("safe-name.txt", download["url"])

        for unsafe_filename in ("../secrets.txt", "/tmp/secret.txt", "nested\\secret.txt", "bad\nname.txt"):
            with self.assertRaises(Exception) as raised:
                self.store.create_file_object("usr_test_actor", {"filename": unsafe_filename, "content_type": "text/plain", "size_bytes": 1})
            self.assertEqual(getattr(raised.exception, "code", ""), "invalid_input")

    def test_file_upload_download_list_delete_and_audit(self) -> None:
        uploaded = self.store.upload_file_object(
            "usr_test_actor",
            {
                "owner_id": "usr_owner",
                "resource_type": "test_run",
                "resource_id": "trn_001",
                "module": "qa",
                "filename": "result.txt",
                "content_type": "text/plain",
                "content_base64": base64.b64encode(b"passed").decode("ascii"),
            },
        )

        self.assertEqual(uploaded["status"], "available")
        self.assertEqual(uploaded["size_bytes"], 6)
        self.assertIn("checksum", uploaded)
        self.assertNotIn("storage_key", uploaded)

        listed = self.store.list_file_objects({"owner_id": "usr_owner", "resource_type": "test_run", "resource_id": "trn_001", "module": "qa"})
        self.assertEqual([file_object["id"] for file_object in listed], [uploaded["id"]])
        self.assertEqual(self.store.list_file_objects({"module": "ops"}), [])

        downloaded = self.store.download_file_object("usr_test_actor", uploaded["id"], {"owner_id": "usr_owner"})
        self.assertEqual(base64.b64decode(downloaded["content_base64"]), b"passed")
        self.assertEqual(downloaded["file"]["filename"], "result.txt")

        deleted = self.store.delete_file_object("usr_test_actor", uploaded["id"], {"owner_id": "usr_owner"})
        self.assertEqual(deleted["status"], "deleted")
        self.assertEqual(self.store.list_file_objects({"status": "deleted"})[0]["deleted_by"], "usr_test_actor")
        with self.assertRaises(Exception) as raised:
            self.store.download_file_object("usr_test_actor", uploaded["id"], {"owner_id": "usr_owner"})
        self.assertEqual(getattr(raised.exception, "code", ""), "not_found")

        actions = [event["action"] for event in self.store.list_audit_events()]
        self.assertIn("file.uploaded", actions)
        self.assertIn("file.downloaded", actions)
        self.assertIn("file.deleted", actions)

    def test_file_scoped_access_filters_reject_other_owner(self) -> None:
        uploaded = self.store.upload_file_object(
            "usr_test_actor",
            {
                "owner_id": "usr_owner",
                "resource_type": "project",
                "resource_id": "prj_001",
                "module": "reports",
                "filename": "report.txt",
                "content_type": "text/plain",
                "content_base64": base64.b64encode(b"private").decode("ascii"),
            },
        )

        with self.assertRaises(Exception) as raised:
            self.store.download_file_object("usr_test_actor", uploaded["id"], {"owner_id": "usr_other"})
        self.assertEqual(getattr(raised.exception, "code", ""), "not_found")

        with self.assertRaises(Exception) as delete_error:
            self.store.delete_file_object("usr_test_actor", uploaded["id"], {"owner_id": "usr_other"})
        self.assertEqual(getattr(delete_error.exception, "code", ""), "not_found")

    def test_file_upload_rejects_oversized_decoded_content(self) -> None:
        with self.assertRaises(Exception) as raised:
            self.store.upload_file_object(
                "usr_test_actor",
                {
                    "owner_id": "usr_owner",
                    "filename": "too-large.bin",
                    "content_type": "application/octet-stream",
                    "content_base64": base64.b64encode(b"x" * (5 * 1024 * 1024 + 1)).decode("ascii"),
                },
            )
        self.assertEqual(getattr(raised.exception, "code", ""), "invalid_input")

    def test_file_http_routes_enforce_server_owner_scope(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        original_store = FoundationHandler.store
        server = ThreadingHTTPServer(("127.0.0.1", 0), FoundationHandler)
        FoundationHandler.store = MemoryStore(storage=LocalFileStorage(temp_dir.name))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"
        try:
            created = self.http_json(
                base_url,
                "POST",
                "/v1/files/upload",
                {
                    "owner_id": "usr_owner",
                    "filename": "private.txt",
                    "content_type": "text/plain",
                    "content_base64": base64.b64encode(b"private").decode("ascii"),
                },
                {"X-Actor-ID": "usr_owner", "X-Actor-Role": "operator"},
                expected_status=201,
            )

            other_download = self.http_json(
                base_url,
                "GET",
                f"/v1/files/{created['id']}/download",
                headers={"X-Actor-ID": "usr_other", "X-Actor-Role": "operator"},
                expected_status=404,
            )
            self.assertEqual(other_download["error"], "not_found")

            spoofed_list = self.http_json(
                base_url,
                "GET",
                "/v1/files?owner_id=usr_owner",
                headers={"X-Actor-ID": "usr_other", "X-Actor-Role": "operator"},
                expected_status=403,
            )
            self.assertEqual(spoofed_list["error"], "permission_denied")

            owner_download = self.http_json(
                base_url,
                "GET",
                f"/v1/files/{created['id']}/download",
                headers={"X-Actor-ID": "usr_owner", "X-Actor-Role": "operator"},
            )
            self.assertEqual(base64.b64decode(owner_download["content_base64"]), b"private")
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()
            FoundationHandler.store = original_store
            temp_dir.cleanup()

    def http_json(
        self,
        base_url: str,
        method: str,
        path: str,
        body: dict | None = None,
        headers: dict[str, str] | None = None,
        expected_status: int = 200,
    ) -> dict:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(base_url + path, data=data, method=method, headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
                self.assertEqual(response.status, expected_status)
                return payload
        except urllib.error.HTTPError as error:
            payload = json.loads(error.read().decode("utf-8"))
            self.assertEqual(error.code, expected_status)
            return payload

    def test_s3_compatible_storage_requires_bucket_and_defers_client_calls(self) -> None:
        storage = S3CompatibleStorage()
        storage.bucket = "opspilot-files"
        storage.ensure_bucket()
        self.assertEqual(storage.provider, "s3")
        with self.assertRaises(NotImplementedError):
            storage.put("objects/example", b"content")

    def test_credentials_store_secret_references_without_response_secret_leakage(self) -> None:
        credential = self.store.create_credential(
            "usr_test_actor",
            {"provider": "gitlab", "name": "GitLab Ops", "secret": "glpat-secret-value"},
        )

        encoded = json.dumps(credential)
        self.assertNotIn("glpat-secret-value", encoded)
        self.assertIn("secret_ref", credential)
        self.assertIn("secret_fingerprint", credential)
        self.assertTrue(credential["secret_ref"].startswith("sec_"))

        updated = self.store.update_credential("usr_test_actor", credential["id"], {"secret": "rotated-secret-value"})
        self.assertNotEqual(updated["secret_fingerprint"], credential["secret_fingerprint"])
        self.assertNotIn("rotated-secret-value", json.dumps(updated))
        self.assertNotIn("rotated-secret-value", json.dumps(self.store.list_audit_events()))
        self.assertNotIn("secret_fingerprint", json.dumps(self.store.list_audit_events()))

    def test_credential_provider_is_immutable_after_create(self) -> None:
        credential = self.store.create_credential(
            "usr_test_actor",
            {"provider": "gitlab", "name": "GitLab Ops", "secret": "glpat-secret-value"},
        )
        self.store.create_gitlab_profile("usr_test_actor", {"name": "Primary GitLab", "base_url": "https://gitlab.example.com", "credential_ref_id": credential["id"]})

        with self.assertRaises(Exception) as raised:
            self.store.update_credential("usr_test_actor", credential["id"], {"provider": "model_provider"})
        self.assertEqual(getattr(raised.exception, "code", ""), "invalid_input")
        self.assertEqual(self.store.list_credentials()[0]["provider"], "gitlab")

    def test_secret_fingerprint_uses_store_local_hmac_key(self) -> None:
        first = MemoryStore().create_credential("usr_test_actor", {"provider": "gitlab", "name": "GitLab Ops", "secret": "same-secret"})
        second = MemoryStore().create_credential("usr_test_actor", {"provider": "gitlab", "name": "GitLab Ops", "secret": "same-secret"})

        self.assertNotEqual(first["secret_fingerprint"], second["secret_fingerprint"])

    def test_gitlab_profile_repositories_and_project_binding(self) -> None:
        self.store = MemoryStore(gitlab_client=FakeGitLabClient())
        user = self.store.create_user("usr_test_actor", {"email": "admin@example.com", "name": "Admin"})
        project = self.store.create_project("usr_test_actor", {"key": "OPS", "name": "Ops Platform", "owner_id": user["id"]})
        credential = self.store.create_credential(
            "usr_test_actor",
            {"provider": "gitlab", "name": "GitLab Ops", "secret": "glpat-secret-value"},
        )
        profile = self.store.create_gitlab_profile(
            "usr_test_actor",
            {
                "name": "Primary GitLab",
                "base_url": "https://gitlab.example.com",
                "credential_ref_id": credential["id"],
            },
        )
        self.store.sync_gitlab_repositories("usr_test_actor", profile["id"])

        repositories = self.store.list_gitlab_repositories(profile["id"])
        self.assertEqual(repositories[0]["path"], "platform/opspilot")

        linked = self.store.link_project_repository(
            "usr_test_actor",
            project["id"],
            {"provider": "gitlab", "profile_id": profile["id"], "repository_id": "100"},
        )
        self.assertEqual(linked["repository_bindings"][0]["repository_id"], "100")
        self.assertEqual(set(linked["repository_bindings"][0].keys()), {"provider", "profile_id", "repository_id"})

        unlinked = self.store.unlink_project_repository("usr_test_actor", project["id"], profile["id"], "100")
        self.assertEqual(unlinked["repository_bindings"], [])

    def test_gitlab_repository_sync_search_pagination_and_project_binding_audit(self) -> None:
        gitlab = FakeGitLabClient()
        self.store = MemoryStore(gitlab_client=gitlab)
        user = self.store.create_user("usr_test_actor", {"email": "admin@example.com", "name": "Admin"})
        project = self.store.create_project("usr_test_actor", {"key": "OPS", "name": "Ops Platform", "owner_id": user["id"]})
        credential = self.store.create_credential("usr_test_actor", {"provider": "gitlab", "name": "GitLab Ops", "secret": "glpat-secret-value"})
        profile = self.store.create_gitlab_profile(
            "usr_test_actor",
            {"name": "Primary GitLab", "base_url": "https://gitlab.example.com", "credential_ref_id": credential["id"]},
        )

        synced = self.store.sync_gitlab_repositories("usr_test_actor", profile["id"])
        self.assertEqual(synced["total"], 3)
        self.assertTrue(synced["last_synced_at"])

        filtered = self.store.discover_gitlab_repositories(profile["id"], search="platform", page=1, per_page=1)
        self.assertEqual(filtered["total"], 2)
        self.assertEqual(len(filtered["items"]), 1)
        self.assertTrue(filtered["has_next"])

        linked = self.store.link_project_repository("usr_test_actor", project["id"], {"provider": "gitlab", "profile_id": profile["id"], "repository_id": "100"})
        self.assertEqual(linked["repository_bindings"][0], {"provider": "gitlab", "profile_id": profile["id"], "repository_id": "100"})
        audit = json.dumps(self.store.list_audit_events())
        self.assertIn("gitlab.repositories.synced", audit)
        self.assertIn("project.repository.linked", audit)
        self.assertNotIn("glpat-secret-value", audit)

    def test_gitlab_branch_and_merge_request_operations_use_gitlab_client(self) -> None:
        gitlab = FakeGitLabClient()
        self.store = MemoryStore(gitlab_client=gitlab)
        user = self.store.create_user("usr_test_actor", {"email": "admin@example.com", "name": "Admin"})
        project = self.store.create_project("usr_test_actor", {"key": "OPS", "name": "Ops Platform", "owner_id": user["id"]})
        credential = self.store.create_credential(user["id"], {"provider": "gitlab", "name": "GitLab Ops", "secret": "glpat-secret-value"})
        profile = self.store.create_gitlab_profile(
            user["id"],
            {"name": "Primary GitLab", "base_url": "https://gitlab.example.com", "credential_ref_id": credential["id"]},
        )
        self.store.sync_gitlab_repositories(user["id"], profile["id"])
        self.store.link_project_repository(user["id"], project["id"], {"provider": "gitlab", "profile_id": profile["id"], "repository_id": "100"})

        branch_operation = self.store.create_gitlab_branch(user["id"], profile["id"], "100", {"project_id": project["id"], "branch": "feature/gitlab-mvp", "ref": "main"})
        branches = self.store.list_gitlab_branches(user["id"], project["id"], profile["id"], "100")
        merge_operation = self.store.create_gitlab_merge_request(
            user["id"],
            profile["id"],
            "100",
            {"project_id": project["id"], "source_branch": "feature/gitlab-mvp", "target_branch": "main", "title": "GitLab MVP"},
        )
        status = self.store.get_gitlab_merge_request(user["id"], project["id"], profile["id"], "100", merge_operation["external_id"])

        self.assertEqual(branch_operation["status"], "completed")
        self.assertEqual(set(branch_operation["result"]["branch"].keys()), {"name", "default", "protected"})
        self.assertEqual(branches["branches"][1]["name"], "feature/gitlab-mvp")
        self.assertEqual(merge_operation["status"], "completed")
        self.assertEqual(merge_operation["result"]["merge_request"]["state"], "opened")
        self.assertEqual(status["merge_request"]["iid"], merge_operation["external_id"])
        self.assertNotIn("glpat-secret-value", json.dumps({"ops": self.store.list_vcs_operations(), "audit": self.store.list_audit_events()}))

    def test_gitlab_merge_request_failure_records_failed_operation_without_secret_leakage(self) -> None:
        gitlab = FakeGitLabClient()
        gitlab.fail_next_merge_request = True
        self.store = MemoryStore(gitlab_client=gitlab)
        user = self.store.create_user("usr_test_actor", {"email": "admin@example.com", "name": "Admin"})
        project = self.store.create_project("usr_test_actor", {"key": "OPS", "name": "Ops Platform", "owner_id": user["id"]})
        credential = self.store.create_credential(user["id"], {"provider": "gitlab", "name": "GitLab Ops", "secret": "glpat-secret-value"})
        profile = self.store.create_gitlab_profile(
            user["id"],
            {"name": "Primary GitLab", "base_url": "https://gitlab.example.com", "credential_ref_id": credential["id"]},
        )
        self.store.sync_gitlab_repositories(user["id"], profile["id"])
        self.store.link_project_repository(user["id"], project["id"], {"provider": "gitlab", "profile_id": profile["id"], "repository_id": "100"})

        with self.assertRaises(Exception) as raised:
            self.store.create_gitlab_merge_request(
                user["id"],
                profile["id"],
                "100",
                {"project_id": project["id"], "source_branch": "feature/bad", "target_branch": "main", "title": "Bad MR"},
            )

        self.assertEqual(getattr(raised.exception, "code", ""), "invalid_input")
        operations = self.store.list_vcs_operations()
        self.assertEqual(operations[0]["status"], "failed")
        self.assertEqual(operations[0]["operation_type"], "open_merge_request")
        self.assertNotIn("glpat-secret-value", json.dumps({"ops": operations, "audit": self.store.list_audit_events()}))

    def test_gitlab_token_bearing_urls_are_rejected_before_audit_or_response(self) -> None:
        credential = self.store.create_credential(
            "usr_test_actor",
            {"provider": "gitlab", "name": "GitLab Ops", "secret": "glpat-secret-value"},
        )

        with self.assertRaises(Exception) as raised:
            self.store.create_gitlab_profile(
                "usr_test_actor",
                {"name": "Unsafe GitLab", "base_url": "https://oauth2:glpat-token@gitlab.example.com", "credential_ref_id": credential["id"]},
            )
        self.assertEqual(getattr(raised.exception, "code", ""), "invalid_input")
        self.assertNotIn("glpat-token", json.dumps(self.store.list_audit_events()))
        self.assertEqual(self.store.list_gitlab_profiles(), [])

    def test_gitlab_repository_catalog_is_adapter_owned_and_binding_ignores_client_metadata(self) -> None:
        self.store = MemoryStore(gitlab_client=FakeGitLabClient())
        user = self.store.create_user("usr_test_actor", {"email": "admin@example.com", "name": "Admin"})
        project = self.store.create_project("usr_test_actor", {"key": "OPS", "name": "Ops Platform", "owner_id": user["id"]})
        credential = self.store.create_credential(
            "usr_test_actor",
            {"provider": "gitlab", "name": "GitLab Ops", "secret": "glpat-secret-value"},
        )

        with self.assertRaises(Exception) as raised:
            self.store.create_gitlab_profile(
                "usr_test_actor",
                {
                    "name": "Unsafe Repo Selection",
                    "base_url": "https://gitlab.example.com",
                    "credential_ref_id": credential["id"],
                    "repository_selection": [{"id": "100", "path": "platform/opspilot", "web_url": "https://gitlab.example.com/platform/opspilot?private_token=glpat-token"}],
                },
            )
        self.assertEqual(getattr(raised.exception, "code", ""), "invalid_input")

        profile = self.store.create_gitlab_profile(
            "usr_test_actor",
            {
                "name": "Primary GitLab",
                "base_url": "https://gitlab.example.com?utm_source=setup",
                "credential_ref_id": credential["id"],
            },
        )
        self.store.sync_gitlab_repositories("usr_test_actor", profile["id"])
        self.assertEqual(profile["base_url"], "https://gitlab.example.com")

        linked = self.store.link_project_repository(
            "usr_test_actor",
            project["id"],
            {
                "provider": "gitlab",
                "profile_id": profile["id"],
                "repository_id": "100",
                "path": "platform/opspilot",
                "web_url": "https://oauth2:glpat-token@gitlab.example.com/platform/opspilot",
            },
        )
        serialized = json.dumps({"projects": self.store.list_projects(), "repositories": self.store.list_gitlab_repositories(profile["id"]), "audit": self.store.list_audit_events()})
        self.assertEqual(linked["repository_bindings"][0], {"provider": "gitlab", "profile_id": profile["id"], "repository_id": "100"})
        self.assertNotIn("glpat-token", serialized)
        self.assertNotIn("oauth2", serialized)

    def test_gitlab_vcs_operations_and_webhook_events_use_selected_repository(self) -> None:
        self.store = MemoryStore(gitlab_client=FakeGitLabClient())
        credential = self.store.create_credential(
            "usr_test_actor",
            {"provider": "gitlab", "name": "GitLab Ops", "secret": "glpat-secret-value"},
        )
        profile = self.store.create_gitlab_profile(
            "usr_test_actor",
            {
                "name": "Primary GitLab",
                "base_url": "https://gitlab.example.com",
                "credential_ref_id": credential["id"],
                "webhook_secret": "webhook-secret-value",
            },
        )
        self.store.sync_gitlab_repositories("usr_test_actor", profile["id"])

        operation = self.store.create_vcs_operation(
            "usr_test_actor",
            {"provider": "gitlab", "profile_id": profile["id"], "repository_id": "100", "operation_type": "create_branch", "branch": "feature/report-api"},
        )
        webhook = self.store.ingest_vcs_webhook_event(
            "usr_test_actor",
            {
                "provider": "gitlab",
                "profile_id": profile["id"],
                "repository_id": "100",
                "event_type": "merge_request",
                "authenticity_token": "webhook-secret-value",
                "payload": {"iid": 12, "token": "leaked", "nested": {"private_token": "nested-leak", "private_key": "private-key-should-redact", "safe": "value"}},
            },
        )

        self.assertEqual(operation["status"], "completed")
        self.assertEqual(operation["result"]["repository_path"], "platform/opspilot")
        self.assertEqual(webhook["status"], "received")
        self.assertEqual(webhook["payload"]["token"], "[REDACTED]")
        self.assertEqual(webhook["payload"]["nested"]["private_token"], "[REDACTED]")
        self.assertEqual(webhook["payload"]["nested"]["private_key"], "[REDACTED]")
        self.assertEqual(webhook["payload"]["nested"]["safe"], "value")
        serialized = json.dumps({"operations": self.store.list_vcs_operations(), "webhooks": self.store.list_vcs_webhook_events(), "audit": self.store.list_audit_events()})
        self.assertIn("vcs.operation.created", serialized)
        self.assertNotIn("glpat-secret-value", serialized)
        self.assertNotIn("webhook-secret-value", serialized)
        self.assertNotIn("leaked", serialized)
        self.assertNotIn("private-key-should-redact", serialized)

        with self.assertRaises(Exception) as pat_as_webhook_token:
            self.store.ingest_vcs_webhook_event(
                "usr_test_actor",
                {"provider": "gitlab", "profile_id": profile["id"], "repository_id": "100", "event_type": "merge_request", "authenticity_token": "glpat-secret-value"},
            )
        self.assertEqual(getattr(pat_as_webhook_token.exception, "code", ""), "invalid_input")

        with self.assertRaises(Exception) as raised:
            self.store.create_vcs_operation(
                "usr_test_actor",
                {"provider": "gitlab", "profile_id": profile["id"], "repository_id": "missing", "operation_type": "create_branch", "branch": "bad"},
            )
        self.assertEqual(getattr(raised.exception, "code", ""), "not_found")

        with self.assertRaises(Exception) as webhook_error:
            self.store.ingest_vcs_webhook_event(
                "usr_test_actor",
                {"provider": "gitlab", "profile_id": profile["id"], "repository_id": "100", "event_type": "merge_request", "authenticity_token": "wrong"},
            )
        self.assertEqual(getattr(webhook_error.exception, "code", ""), "invalid_input")

    def test_gitlab_branch_and_merge_request_operations_require_bound_project_actor(self) -> None:
        self.store = MemoryStore(gitlab_client=FakeGitLabClient())
        owner = self.store.create_user("usr_test_actor", {"email": "owner@example.com", "name": "Owner"})
        outsider = self.store.create_user("usr_test_actor", {"email": "outsider@example.com", "name": "Outsider"})
        project = self.store.create_project("usr_test_actor", {"key": "OPS", "name": "Ops Platform", "owner_id": owner["id"]})
        credential = self.store.create_credential(owner["id"], {"provider": "gitlab", "name": "GitLab Ops", "secret": "glpat-secret-value"})
        profile = self.store.create_gitlab_profile(owner["id"], {"name": "Primary GitLab", "base_url": "https://gitlab.example.com", "credential_ref_id": credential["id"]})
        self.store.sync_gitlab_repositories(owner["id"], profile["id"])

        with self.assertRaises(PermissionDenied):
            self.store.create_gitlab_branch("system", profile["id"], "100", {"project_id": project["id"], "branch": "feature/no-auth", "ref": "main"})
        with self.assertRaises(Exception) as unbound:
            self.store.create_gitlab_branch(owner["id"], profile["id"], "100", {"project_id": project["id"], "branch": "feature/unbound", "ref": "main"})
        self.assertEqual(getattr(unbound.exception, "code", ""), "conflict")

        self.store.link_project_repository(owner["id"], project["id"], {"provider": "gitlab", "profile_id": profile["id"], "repository_id": "100"})
        with self.assertRaises(PermissionDenied):
            self.store.create_gitlab_branch(outsider["id"], profile["id"], "100", {"project_id": project["id"], "branch": "feature/outsider", "ref": "main"})
        allowed = self.store.create_gitlab_branch(owner["id"], profile["id"], "100", {"project_id": project["id"], "branch": "feature/owner", "ref": "main"})
        self.assertEqual(allowed["status"], "completed")

    def test_agent_skill_model_provider_and_workflow_slice(self) -> None:
        credential = self.store.create_credential(
            "usr_test_actor",
            {"provider": "model_provider", "name": "OpenAI Ops", "secret": "sk-secret-value"},
        )
        provider = self.store.create_model_provider(
            "usr_test_actor",
            {
                "provider": "openai",
                "name": "OpenAI Default",
                "credential_ref_id": credential["id"],
                "base_url": "https://api.openai.example.com/v1?utm_source=setup",
                "models": ["gpt-4.1", "gpt-4.1", "gpt-4.1-mini"],
            },
        )
        self.assertEqual(provider["base_url"], "https://api.openai.example.com/v1")
        self.assertEqual(provider["models"], ["gpt-4.1", "gpt-4.1-mini"])
        self.assertNotIn("sk-secret-value", json.dumps(provider))

        skill = self.store.create_skill(
            "usr_test_actor",
            {"name": "Incident Triage", "version": "1.0.0", "runtime": "python", "capabilities": ["triage", "summarize"]},
        )
        agent = self.store.create_agent(
            "usr_test_actor",
            {
                "name": "Ops Copilot",
                "kind": "automation",
                "capabilities": ["triage", "triage"],
                "skill_ids": [skill["id"]],
                "model_provider_id": provider["id"],
            },
        )
        self.assertEqual(agent["capabilities"], ["triage"])

        workflow = self.store.create_workflow("usr_test_actor", {"name": "Incident response", "description": "Triage and summarize"})
        version = self.store.create_workflow_version(
            "usr_test_actor",
            workflow["id"],
            {
                "version": "1",
                "nodes": [
                    {"id": "start", "type": "trigger", "name": "Alert received"},
                    {"id": "triage", "type": "agent_task", "agent_id": agent["id"], "skill_id": skill["id"], "model_provider_id": provider["id"]},
                ],
                "edges": [{"from_node_id": "start", "to_node_id": "triage"}],
            },
        )
        self.assertEqual(version["workflow_id"], workflow["id"])
        self.assertEqual(self.store.list_workflows()[0]["active_version_id"], version["id"])

        with self.assertRaises(Exception) as raised:
            self.store.create_workflow_version(
                "usr_test_actor",
                workflow["id"],
                {
                    "version": "bad",
                    "nodes": [{"id": "start", "type": "trigger"}],
                    "edges": [{"from_node_id": "start", "to_node_id": "missing"}],
                },
            )
        self.assertEqual(getattr(raised.exception, "code", ""), "invalid_input")

        audit = json.dumps(self.store.list_audit_events())
        self.assertIn("workflow.version.created", audit)
        self.assertIn("agent.created", audit)
        self.assertNotIn("sk-secret-value", audit)

    def test_agent_workflow_security_boundaries(self) -> None:
        first_credential = self.store.create_credential("usr_test_actor", {"provider": "model_provider", "name": "Model Key 1", "secret": "sk-one"})
        second_credential = self.store.create_credential("usr_test_actor", {"provider": "model_provider", "name": "Model Key 2", "secret": "sk-two"})
        first_provider = self.store.create_model_provider("usr_test_actor", {"provider": "openai", "name": "Provider 1", "credential_ref_id": first_credential["id"]})
        second_provider = self.store.create_model_provider("usr_test_actor", {"provider": "anthropic", "name": "Provider 2", "credential_ref_id": second_credential["id"]})
        allowed_skill = self.store.create_skill("usr_test_actor", {"name": "Allowed Skill", "version": "1.0.0", "runtime": "python"})
        other_skill = self.store.create_skill("usr_test_actor", {"name": "Other Skill", "version": "1.0.0", "runtime": "python"})
        agent = self.store.create_agent(
            "usr_test_actor",
            {"name": "Guarded Agent", "kind": "automation", "skill_ids": [allowed_skill["id"]], "model_provider_id": first_provider["id"]},
        )

        with self.assertRaises(Exception) as credential_delete_error:
            self.store.delete_credential("usr_test_actor", first_credential["id"])
        self.assertEqual(getattr(credential_delete_error.exception, "code", ""), "conflict")
        self.assertEqual(self.store.list_credentials()[0]["id"], first_credential["id"])

        first_workflow = self.store.create_workflow("usr_test_actor", {"name": "Workflow A"})
        second_workflow = self.store.create_workflow("usr_test_actor", {"name": "Workflow B"})
        first_version = self.store.create_workflow_version(
            "usr_test_actor",
            first_workflow["id"],
            {"version": "1", "nodes": [{"id": "start", "type": "trigger"}]},
        )
        with self.assertRaises(Exception) as cross_workflow_error:
            self.store.update_workflow("usr_test_actor", second_workflow["id"], {"active_version_id": first_version["id"]})
        self.assertEqual(getattr(cross_workflow_error.exception, "code", ""), "conflict")
        workflow_after_rejected_update = next(workflow for workflow in self.store.list_workflows() if workflow["id"] == second_workflow["id"])
        self.assertEqual(workflow_after_rejected_update["active_version_id"], "")

        with self.assertRaises(Exception) as skill_policy_error:
            self.store.create_workflow_version(
                "usr_test_actor",
                first_workflow["id"],
                {
                    "version": "bad-skill",
                    "nodes": [{"id": "task", "type": "agent_task", "agent_id": agent["id"], "skill_id": other_skill["id"], "model_provider_id": first_provider["id"]}],
                },
            )
        self.assertEqual(getattr(skill_policy_error.exception, "code", ""), "conflict")

        with self.assertRaises(Exception) as provider_policy_error:
            self.store.create_workflow_version(
                "usr_test_actor",
                first_workflow["id"],
                {
                    "version": "bad-provider",
                    "nodes": [{"id": "task", "type": "agent_task", "agent_id": agent["id"], "skill_id": allowed_skill["id"], "model_provider_id": second_provider["id"]}],
                },
            )
        self.assertEqual(getattr(provider_policy_error.exception, "code", ""), "conflict")

    def test_workflow_run_execution_slice_orders_and_transitions_steps(self) -> None:
        credential = self.store.create_credential("usr_test_actor", {"provider": "model_provider", "name": "Model Key", "secret": "sk-secret"})
        provider = self.store.create_model_provider("usr_test_actor", {"provider": "openai", "name": "Provider", "credential_ref_id": credential["id"]})
        skill = self.store.create_skill("usr_test_actor", {"name": "Deploy", "version": "1.0.0", "runtime": "python"})
        agent = self.store.create_agent("usr_test_actor", {"name": "Deploy Agent", "kind": "automation", "skill_ids": [skill["id"]], "model_provider_id": provider["id"]})
        workflow = self.store.create_workflow("usr_test_actor", {"name": "Deploy workflow"})
        version = self.store.create_workflow_version(
            "usr_test_actor",
            workflow["id"],
            {
                "version": "1",
                "nodes": [
                    {"id": "approve", "type": "approval", "name": "Approve"},
                    {"id": "start", "type": "trigger", "name": "Start"},
                    {"id": "deploy", "type": "agent_task", "name": "Deploy", "agent_id": agent["id"], "skill_id": skill["id"], "model_provider_id": provider["id"]},
                    {"id": "done", "type": "result", "name": "Done"},
                ],
                "edges": [
                    {"from_node_id": "start", "to_node_id": "deploy"},
                    {"from_node_id": "deploy", "to_node_id": "approve"},
                    {"from_node_id": "approve", "to_node_id": "done"},
                ],
            },
        )

        run = self.store.create_workflow_run("usr_test_actor", workflow["id"], {})
        self.assertEqual(run["workflow_version_id"], version["id"])
        self.assertEqual(run["status"], "created")
        self.assertEqual([step["node_id"] for step in run["steps"]], ["start", "deploy", "approve", "done"])
        self.assertEqual([step["step_type"] for step in run["steps"]], ["trigger", "agent", "manual", "result"])
        self.assertEqual(next(step for step in run["steps"] if step["node_id"] == "done")["predecessor_node_ids"], ["approve"])

        started = self.store.start_workflow_run("usr_test_actor", run["id"])
        self.assertEqual(started["status"], "running")
        self.assertEqual(started["steps"][0]["status"], "completed")

        agent_step = next(step for step in started["steps"] if step["step_type"] == "agent")
        manual_step = next(step for step in started["steps"] if step["step_type"] == "manual")
        result_step = next(step for step in started["steps"] if step["step_type"] == "result")
        running = self.store.update_workflow_step_run("usr_test_actor", run["id"], agent_step["id"], {"status": "running"})
        self.assertEqual(next(step for step in running["steps"] if step["id"] == agent_step["id"])["status"], "running")
        self.store.update_workflow_step_run("usr_test_actor", run["id"], agent_step["id"], {"status": "completed", "output": {"deployment_id": "dep-1"}})

        with self.assertRaises(Exception) as skipped_gate:
            self.store.update_workflow_step_run("usr_test_actor", run["id"], manual_step["id"], {"status": "skipped"})
        self.assertEqual(getattr(skipped_gate.exception, "code", ""), "invalid_input")

        self.store.update_workflow_version(
            "usr_test_actor",
            workflow["id"],
            version["id"],
            {
                "edges": [
                    {"from_node_id": "start", "to_node_id": "deploy"},
                    {"from_node_id": "deploy", "to_node_id": "done"},
                    {"from_node_id": "done", "to_node_id": "approve"},
                ],
            },
        )
        with self.assertRaises(Exception) as downstream_bypass:
            self.store.update_workflow_step_run("usr_test_actor", run["id"], result_step["id"], {"status": "completed", "output": {"summary": "bypassed"}})
        self.assertEqual(getattr(downstream_bypass.exception, "code", ""), "conflict")
        self.assertEqual(self.store.list_workflow_runs(workflow["id"])[0]["status"], "running")
        self.assertEqual(next(step for step in self.store.list_workflow_runs(workflow["id"])[0]["steps"] if step["node_id"] == "done")["predecessor_node_ids"], ["approve"])

        self.store.update_workflow_step_run("usr_test_actor", run["id"], manual_step["id"], {"status": "completed", "output": {"approved_by": "qa"}})
        completed = self.store.update_workflow_step_run("usr_test_actor", run["id"], result_step["id"], {"status": "completed", "output": {"summary": "ok"}})

        self.assertEqual(completed["status"], "completed")
        self.assertTrue(completed["completed_at"])
        self.assertEqual(next(step for step in completed["steps"] if step["id"] == agent_step["id"])["output"], {"deployment_id": "dep-1"})
        self.assertEqual(self.store.list_workflow_runs(workflow["id"])[0]["id"], run["id"])

        with self.assertRaises(Exception) as raised:
            self.store.update_workflow_step_run("usr_test_actor", run["id"], agent_step["id"], {"status": "running"})
        self.assertEqual(getattr(raised.exception, "code", ""), "conflict")

        audit = json.dumps(self.store.list_audit_events())
        self.assertIn("workflow.run.created", audit)
        self.assertIn("workflow.run.started", audit)
        self.assertIn("workflow.step.updated", audit)
        self.assertNotIn("sk-secret", audit)

    def test_test_report_quality_gate_slice_validates_project_boundaries(self) -> None:
        user = self.store.create_user("usr_test_actor", {"email": "admin@example.com", "name": "Admin"})
        project = self.store.create_project("usr_test_actor", {"key": "OPS", "name": "Ops Platform", "owner_id": user["id"]})
        other_project = self.store.create_project("usr_test_actor", {"key": "OTHER", "name": "Other Platform", "owner_id": user["id"]})
        environment = self.store.create_environment(
            "usr_test_actor",
            {"project_id": project["id"], "name": "QA Lab", "type": "QA", "owner_id": user["id"]},
        )

        test_case = self.store.create_test_case(
            "usr_test_actor",
            {"project_id": project["id"], "name": "Login smoke", "case_type": "automated", "steps": [{"action": "open", "expected": "login form"}]},
        )
        suite = self.store.create_test_suite("usr_test_actor", {"project_id": project["id"], "name": "Smoke", "case_ids": [test_case["id"], test_case["id"]]})
        run = self.store.create_test_run("usr_test_actor", {"project_id": project["id"], "suite_id": suite["id"], "environment_id": environment["id"]})
        updated_run = self.store.update_test_run("usr_test_actor", run["id"], {"status": "passed", "results": [{"case_id": test_case["id"], "status": "passed"}]})
        artifact = self.store.upload_file_object(
            "usr_test_actor",
            {
                "owner_id": user["id"],
                "resource_type": "test_run",
                "resource_id": run["id"],
                "module": "reports",
                "filename": "qa-report.md",
                "content_type": "text/markdown",
                "content_base64": base64.b64encode(b"qa report").decode("ascii"),
            },
        )
        report = self.store.create_report(
            user["id"],
            {"project_id": project["id"], "title": "QA Smoke Report", "test_run_id": run["id"], "file_ids": [artifact["id"]], "summary": {"passed": 1}},
        )
        gate = self.store.create_quality_gate(
            "usr_test_actor",
            {"project_id": project["id"], "name": "Smoke Gate", "last_report_id": report["id"], "status": "passed", "conditions": [{"metric": "failed", "equals": 0}]},
        )

        self.assertEqual(suite["case_ids"], [test_case["id"]])
        self.assertEqual(updated_run["status"], "passed")
        self.assertEqual(report["file_ids"], [artifact["id"]])
        self.assertEqual(gate["status"], "passed")

        with self.assertRaises(Exception) as raised:
            self.store.create_test_suite("usr_test_actor", {"project_id": other_project["id"], "name": "Bad Suite", "case_ids": [test_case["id"]]})
        self.assertEqual(getattr(raised.exception, "code", ""), "conflict")

        other_project_artifact = self.store.upload_file_object(
            "usr_test_actor",
            {
                "owner_id": user["id"],
                "resource_type": "project",
                "resource_id": other_project["id"],
                "module": "reports",
                "filename": "other-project.md",
                "content_type": "text/markdown",
                "content_base64": base64.b64encode(b"wrong project").decode("ascii"),
            },
        )
        with self.assertRaises(Exception) as cross_project_file:
            self.store.create_report(user["id"], {"project_id": project["id"], "title": "Bad File Project", "file_ids": [other_project_artifact["id"]]})
        self.assertEqual(getattr(cross_project_file.exception, "code", ""), "conflict")

        with self.assertRaises(PermissionDenied):
            self.store.create_report("usr_project_outsider", {"project_id": project["id"], "title": "Outsider Report", "file_ids": [artifact["id"]]})

        other_owner_artifact = self.store.upload_file_object(
            "usr_test_actor",
            {
                "owner_id": "usr_other",
                "resource_type": "project",
                "resource_id": project["id"],
                "module": "reports",
                "filename": "other-owner.md",
                "content_type": "text/markdown",
                "content_base64": base64.b64encode(b"wrong owner").decode("ascii"),
            },
        )
        with self.assertRaises(Exception) as cross_owner_file:
            self.store.create_report(user["id"], {"project_id": project["id"], "title": "Bad File Owner", "file_ids": [other_owner_artifact["id"]]})
        self.assertEqual(getattr(cross_owner_file.exception, "code", ""), "conflict")

        audit = json.dumps(self.store.list_audit_events())
        self.assertIn("test_run.updated", audit)
        self.assertIn("report.created", audit)
        self.assertIn("quality_gate.created", audit)


if __name__ == "__main__":
    unittest.main()
