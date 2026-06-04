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
        self.assertNotIn("storage_key", file_object)
        self.assertTrue(upload["url"].startswith("local://uploads/objects/"))
        self.assertTrue(download["url"].startswith("local://downloads/objects/"))
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
            {"provider": "gitlab", "profile_id": profile["id"], "repository_id": "100"},
        )
        self.assertEqual(linked["repository_bindings"][0]["repository_id"], "100")
        self.assertEqual(linked["repository_bindings"][0]["path"], "platform/opspilot")

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

    def test_gitlab_vcs_operations_and_webhook_events_use_selected_repository(self) -> None:
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
                "repository_selection": [{"id": "100", "path": "platform/opspilot", "name": "OpsPilot"}],
            },
        )

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
                "authenticity_token": "glpat-secret-value",
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
        self.assertNotIn("leaked", serialized)
        self.assertNotIn("private-key-should-redact", serialized)

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
        artifact = self.store.create_file_object("usr_test_actor", {"filename": "qa-report.md", "content_type": "text/markdown", "size_bytes": 128})

        test_case = self.store.create_test_case(
            "usr_test_actor",
            {"project_id": project["id"], "name": "Login smoke", "case_type": "automated", "steps": [{"action": "open", "expected": "login form"}]},
        )
        suite = self.store.create_test_suite("usr_test_actor", {"project_id": project["id"], "name": "Smoke", "case_ids": [test_case["id"], test_case["id"]]})
        run = self.store.create_test_run("usr_test_actor", {"project_id": project["id"], "suite_id": suite["id"], "environment_id": environment["id"]})
        updated_run = self.store.update_test_run("usr_test_actor", run["id"], {"status": "passed", "results": [{"case_id": test_case["id"], "status": "passed"}]})
        report = self.store.create_report(
            "usr_test_actor",
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

        audit = json.dumps(self.store.list_audit_events())
        self.assertIn("test_run.updated", audit)
        self.assertIn("report.created", audit)
        self.assertIn("quality_gate.created", audit)


if __name__ == "__main__":
    unittest.main()
