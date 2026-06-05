from __future__ import annotations

from typing import Any

from .gateway import FakeModelGateway


class ControlledSkillExecutor:
    """Runs only built-in deterministic skill behavior for local worker smoke tests."""

    def __init__(self, model_gateway: FakeModelGateway | None = None) -> None:
        self.model_gateway = model_gateway or FakeModelGateway()

    def execute(self, task: dict[str, Any], skill: dict[str, Any] | None, provider: dict[str, Any] | None) -> dict[str, Any]:
        skill_name = str((skill or {}).get("name", "")).strip().lower()
        if "fail" in skill_name:
            return {"status": "failed", "error": "controlled skill requested failure", "retry": True}

        model_result = self.model_gateway.complete(task, provider)
        output: dict[str, Any] = {
            "worker": "opspilot-local-agent-worker",
            "node_id": task.get("node_id", ""),
            "agent_id": task.get("agent_id", ""),
            "skill_id": task.get("skill_id", ""),
            "binding_names": task.get("input_summary", {}).get("binding_names", []),
        }
        if model_result:
            output["model"] = {
                "provider_id": model_result.provider_id,
                "provider": model_result.provider,
                "message": model_result.message,
            }
        return {"status": "completed", "output": output}
