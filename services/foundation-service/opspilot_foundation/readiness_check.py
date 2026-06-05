from __future__ import annotations

import json
import os
import sys
from typing import Any
from urllib.request import urlopen


def is_ready(payload: dict[str, Any]) -> bool:
    if payload.get("status") != "ok":
        return False
    dependencies = payload.get("dependencies", {})
    if not isinstance(dependencies, dict):
        return False
    for dependency in dependencies.values():
        if not isinstance(dependency, dict) or dependency.get("status") != "ok":
            return False
    store = dependencies.get("store", {})
    if not isinstance(store, dict):
        return False
    return store.get("migration_status") in {"ok", "not_applicable"}


def main() -> None:
    url = os.environ.get("OPSPILOT_READINESS_URL", "http://127.0.0.1:8080/readyz")
    with urlopen(url, timeout=3) as response:
        payload = json.loads(response.read().decode("utf-8"))
    raise SystemExit(0 if is_ready(payload) else 1)


if __name__ == "__main__":
    main()
