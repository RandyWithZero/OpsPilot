from __future__ import annotations

import argparse
import os

from .api import FoundationAPIClient
from .worker import AgentWorker, WorkerConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local OpsPilot agent worker")
    parser.add_argument("--foundation-url", default=os.environ.get("OPSPILOT_FOUNDATION_URL", "http://127.0.0.1:8080"))
    parser.add_argument("--access-token", default=os.environ.get("OPSPILOT_WORKER_ACCESS_TOKEN", ""))
    parser.add_argument("--worker-id", default=os.environ.get("OPSPILOT_WORKER_ID", "local-agent-worker"))
    parser.add_argument("--agent-id", default=os.environ.get("OPSPILOT_WORKER_AGENT_ID", ""))
    parser.add_argument("--lease-seconds", type=int, default=int(os.environ.get("OPSPILOT_WORKER_LEASE_SECONDS", "60")))
    parser.add_argument("--poll-interval-seconds", type=float, default=float(os.environ.get("OPSPILOT_WORKER_POLL_INTERVAL_SECONDS", "2")))
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if not args.access_token:
        raise SystemExit("OPSPILOT_WORKER_ACCESS_TOKEN or --access-token is required")

    api = FoundationAPIClient(args.foundation_url, args.access_token)
    worker = AgentWorker(
        api,
        WorkerConfig(
            worker_id=args.worker_id,
            agent_id=args.agent_id,
            lease_seconds=args.lease_seconds,
            poll_interval_seconds=args.poll_interval_seconds,
            once=args.once,
        ),
    )
    worker.install_signal_handlers()
    worker.run_forever()


if __name__ == "__main__":
    main()
