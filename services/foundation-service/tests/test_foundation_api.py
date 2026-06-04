import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from opspilot_foundation.store import MemoryStore  # noqa: E402


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

    def test_json_contract_uses_snake_case(self) -> None:
        user = self.store.create_user("usr_test_actor", {"email": "admin@example.com", "name": "Admin"})
        encoded = json.dumps(user)
        self.assertIn("created_at", encoded)
        self.assertNotIn("createdAt", encoded)


if __name__ == "__main__":
    unittest.main()
