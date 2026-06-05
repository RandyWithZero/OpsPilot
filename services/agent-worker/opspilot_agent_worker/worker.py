from __future__ import annotations

import signal
import time
from dataclasses import dataclass
from typing import Any

from .api import FoundationAPIClient, NoRuntimeTask
from .skills import ControlledSkillExecutor


@dataclass
class WorkerConfig:
    worker_id: str = "local-agent-worker"
    agent_id: str = ""
    lease_seconds: int = 60
    poll_interval_seconds: float = 2.0
    once: bool = False


class AgentWorker:
    def __init__(self, api: FoundationAPIClient, config: WorkerConfig | None = None, executor: ControlledSkillExecutor | None = None) -> None:
        self.api = api
        self.config = config or WorkerConfig()
        self.executor = executor or ControlledSkillExecutor()
        self._stopping = False

    def install_signal_handlers(self) -> None:
        signal.signal(signal.SIGINT, self._request_stop)
        signal.signal(signal.SIGTERM, self._request_stop)

    def run_forever(self) -> None:
        while not self._stopping:
            processed = self.poll_once()
            if self.config.once:
                return
            if not processed:
                time.sleep(self.config.poll_interval_seconds)

    def poll_once(self) -> bool:
        try:
            task = self.api.claim_runtime_task(agent_id=self.config.agent_id, worker_id=self.config.worker_id, lease_seconds=self.config.lease_seconds)
        except NoRuntimeTask:
            return False

        token = str(task["attempt_token"])
        self.api.callback_runtime_task(task["id"], {"attempt_token": token, "status": "running", "lease_seconds": self.config.lease_seconds})
        try:
            skill = self._by_id(self.api.list_skills(), str(task.get("skill_id", "")))
            provider = self._by_id(self.api.list_model_providers(), str(task.get("model_provider_id", "")))
            result = self.executor.execute(task, skill, provider)
        except Exception as exc:
            result = {"status": "failed", "error": str(exc), "retry": True}

        callback: dict[str, Any] = {"attempt_token": token, "status": result["status"]}
        if "output" in result:
            callback["output"] = result["output"]
        if "error" in result:
            callback["error"] = result["error"]
        if result.get("retry") is True:
            callback["retry"] = True
        run = self.api.callback_runtime_task(task["id"], callback)
        if callback["status"] == "completed":
            self._complete_ready_result_steps(run, callback.get("output", {}))
        return True

    def stop(self) -> None:
        self._stopping = True

    def _request_stop(self, signum: int, frame: Any) -> None:
        self.stop()

    def _by_id(self, records: list[dict[str, Any]], record_id: str) -> dict[str, Any] | None:
        if not record_id:
            return None
        return next((record for record in records if record.get("id") == record_id), None)

    def _complete_ready_result_steps(self, run: dict[str, Any], output: dict[str, Any]) -> None:
        completed_nodes = {str(step.get("node_id", "")) for step in run.get("steps", []) if step.get("status") in {"completed", "skipped"}}
        for step in run.get("steps", []):
            if step.get("step_type") != "result" or step.get("status") != "pending":
                continue
            predecessors = [str(node_id) for node_id in step.get("predecessor_node_ids", [])]
            if all(node_id in completed_nodes for node_id in predecessors):
                updated = self.api.update_workflow_step(run["id"], step["id"], {"status": "completed", "output": {"runtime_output": output}})
                completed_nodes = {str(candidate.get("node_id", "")) for candidate in updated.get("steps", []) if candidate.get("status") in {"completed", "skipped"}}
