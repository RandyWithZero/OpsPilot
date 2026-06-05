ALTER TABLE workflow_runtime_tasks
  ADD COLUMN worker_id VARCHAR(128) NOT NULL DEFAULT '',
  ADD COLUMN heartbeat_at VARCHAR(64) NOT NULL DEFAULT '',
  ADD COLUMN lease_expires_at VARCHAR(64) NOT NULL DEFAULT '';
