from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ModelGatewayResult:
    provider_id: str
    provider: str
    message: str


class FakeModelGateway:
    """Deterministic model boundary; it consumes provider refs, not raw secrets."""

    def complete(self, task: dict[str, Any], provider: dict[str, Any] | None) -> ModelGatewayResult | None:
        if not provider:
            return None
        provider_id = str(provider.get("id", ""))
        provider_name = str(provider.get("provider", "") or provider.get("name", "") or "local")
        node_id = str(task.get("node_id", ""))
        return ModelGatewayResult(provider_id=provider_id, provider=provider_name, message=f"fake model completion for {node_id}")
