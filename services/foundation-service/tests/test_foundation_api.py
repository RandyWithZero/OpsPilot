import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from opspilot_foundation.store import MemoryStore  # noqa: E402
from opspilot_foundation.server import FoundationHandler  # noqa: E402


class FoundationSliceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = MemoryStore()

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
            {"category": "workstation", "name": "ws-01", "owner_id": user["id"], "capabilities": ["gpu", "linux", "gpu"]},
        )
        self.assertEqual(asset["capabilities"], ["gpu", "linux"])

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
        self.assertIn(("Access-Control-Allow-Headers", "Content-Type,X-Actor-ID"), headers)

    def test_file_grants_are_metadata_only(self) -> None:
        file_object = self.store.create_file_object(
            "usr_test_actor",
            {"filename": "report.txt", "content_type": "text/plain", "size_bytes": 1024, "owner_id": "usr_external"},
        )

        upload = self.store.create_upload_grant("usr_test_actor", file_object["id"])
        download = self.store.create_download_grant("usr_test_actor", file_object["id"])

        self.assertEqual(upload["method"], "PUT")
        self.assertEqual(download["method"], "GET")
        self.assertIn(file_object["storage_key"], upload["url"])
        self.assertIn(file_object["storage_key"], download["url"])

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

    def test_secret_fingerprint_uses_store_local_hmac_key(self) -> None:
        first = MemoryStore().create_credential("usr_test_actor", {"provider": "gitlab", "name": "GitLab Ops", "secret": "same-secret"})
        second = MemoryStore().create_credential("usr_test_actor", {"provider": "gitlab", "name": "GitLab Ops", "secret": "same-secret"})

        self.assertNotEqual(first["secret_fingerprint"], second["secret_fingerprint"])

    def test_gitlab_profile_repositories_and_project_binding(self) -> None:
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
                "repository_selection": [
                    {"id": "100", "path": "platform/opspilot", "name": "OpsPilot", "web_url": "https://gitlab.example.com/platform/opspilot"}
                ],
            },
        )

        repositories = self.store.list_gitlab_repositories(profile["id"])
        self.assertEqual(repositories[0]["path"], "platform/opspilot")

        linked = self.store.link_project_repository(
            "usr_test_actor",
            project["id"],
            {"provider": "gitlab", "profile_id": profile["id"], "repository_id": "100", "path": "platform/opspilot"},
        )
        self.assertEqual(linked["repository_bindings"][0]["repository_id"], "100")

        unlinked = self.store.unlink_project_repository("usr_test_actor", project["id"], profile["id"], "100")
        self.assertEqual(unlinked["repository_bindings"], [])

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

    def test_gitlab_repository_urls_are_sanitized_and_binding_ignores_client_web_url(self) -> None:
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
                "repository_selection": [{"id": "100", "path": "platform/opspilot", "web_url": "https://gitlab.example.com/platform/opspilot?tab=readme"}],
            },
        )
        self.assertEqual(profile["base_url"], "https://gitlab.example.com")
        self.assertEqual(profile["repository_selection"][0]["web_url"], "https://gitlab.example.com/platform/opspilot")

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
        self.assertEqual(linked["repository_bindings"][0]["web_url"], "https://gitlab.example.com/platform/opspilot")
        self.assertNotIn("glpat-token", serialized)
        self.assertNotIn("oauth2", serialized)


if __name__ == "__main__":
    unittest.main()
