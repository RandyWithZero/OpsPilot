CREATE TABLE IF NOT EXISTS foundation_schema_migrations (
  version VARCHAR(128) NOT NULL PRIMARY KEY,
  applied_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS users (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
  email VARCHAR(255) NOT NULL,
  name VARCHAR(255) NOT NULL,
  status VARCHAR(32) NOT NULL,
  roles JSON NOT NULL,
  payload JSON NOT NULL,
  created_at VARCHAR(64) NOT NULL,
  updated_at VARCHAR(64) NOT NULL,
  UNIQUE KEY ux_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS projects (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
  project_key VARCHAR(64) NOT NULL,
  name VARCHAR(255) NOT NULL,
  owner_id VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL,
  payload JSON NOT NULL,
  created_at VARCHAR(64) NOT NULL,
  updated_at VARCHAR(64) NOT NULL,
  UNIQUE KEY ux_projects_key (project_key),
  KEY ix_projects_owner (owner_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS project_members (
  project_id VARCHAR(64) NOT NULL,
  user_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (project_id, user_id),
  CONSTRAINT fk_project_members_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS assets (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
  category VARCHAR(64) NOT NULL,
  name VARCHAR(255) NOT NULL,
  status VARCHAR(32) NOT NULL,
  owner_id VARCHAR(64) NOT NULL DEFAULT '',
  parent_id VARCHAR(64) NOT NULL DEFAULT '',
  payload JSON NOT NULL,
  created_at VARCHAR(64) NOT NULL,
  updated_at VARCHAR(64) NOT NULL,
  KEY ix_assets_category_status (category, status),
  KEY ix_assets_owner (owner_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS environments (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
  project_id VARCHAR(64) NOT NULL,
  name VARCHAR(255) NOT NULL,
  environment_type VARCHAR(16) NOT NULL,
  owner_id VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL,
  payload JSON NOT NULL,
  created_at VARCHAR(64) NOT NULL,
  updated_at VARCHAR(64) NOT NULL,
  KEY ix_environments_project (project_id, status),
  CONSTRAINT fk_environments_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS project_assets (
  project_id VARCHAR(64) NOT NULL,
  asset_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (project_id, asset_id),
  CONSTRAINT fk_project_assets_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
  CONSTRAINT fk_project_assets_asset FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS project_environments (
  project_id VARCHAR(64) NOT NULL,
  environment_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (project_id, environment_id),
  CONSTRAINT fk_project_environments_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
  CONSTRAINT fk_project_environments_environment FOREIGN KEY (environment_id) REFERENCES environments(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS environment_members (
  environment_id VARCHAR(64) NOT NULL,
  user_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (environment_id, user_id),
  CONSTRAINT fk_environment_members_environment FOREIGN KEY (environment_id) REFERENCES environments(id) ON DELETE CASCADE,
  CONSTRAINT fk_environment_members_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS environment_assets (
  environment_id VARCHAR(64) NOT NULL,
  asset_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (environment_id, asset_id),
  CONSTRAINT fk_environment_assets_environment FOREIGN KEY (environment_id) REFERENCES environments(id) ON DELETE CASCADE,
  CONSTRAINT fk_environment_assets_asset FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS credentials (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
  provider VARCHAR(64) NOT NULL,
  name VARCHAR(255) NOT NULL,
  secret_ref VARCHAR(128) NOT NULL,
  secret_fingerprint VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL,
  payload JSON NOT NULL,
  created_at VARCHAR(64) NOT NULL,
  updated_at VARCHAR(64) NOT NULL,
  KEY ix_credentials_provider_status (provider, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS secret_refs (
  secret_ref VARCHAR(128) NOT NULL PRIMARY KEY,
  secret_value TEXT NOT NULL,
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS gitlab_profiles (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  base_url VARCHAR(512) NOT NULL,
  credential_ref_id VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL,
  payload JSON NOT NULL,
  created_at VARCHAR(64) NOT NULL,
  updated_at VARCHAR(64) NOT NULL,
  UNIQUE KEY ux_gitlab_profiles_name (name),
  CONSTRAINT fk_gitlab_profiles_credential FOREIGN KEY (credential_ref_id) REFERENCES credentials(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS project_repository_bindings (
  project_id VARCHAR(64) NOT NULL,
  provider VARCHAR(32) NOT NULL,
  profile_id VARCHAR(64) NOT NULL,
  repository_id VARCHAR(255) NOT NULL,
  PRIMARY KEY (project_id, provider, profile_id, repository_id),
  CONSTRAINT fk_project_repository_bindings_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
  CONSTRAINT fk_project_repository_bindings_profile FOREIGN KEY (profile_id) REFERENCES gitlab_profiles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS files (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
  filename VARCHAR(255) NOT NULL,
  content_type VARCHAR(255) NOT NULL,
  size_bytes BIGINT UNSIGNED NOT NULL,
  owner_id VARCHAR(64) NOT NULL DEFAULT '',
  resource_type VARCHAR(64) NOT NULL DEFAULT '',
  resource_id VARCHAR(64) NOT NULL DEFAULT '',
  module VARCHAR(64) NOT NULL DEFAULT '',
  status VARCHAR(32) NOT NULL,
  payload JSON NOT NULL,
  created_at VARCHAR(64) NOT NULL,
  updated_at VARCHAR(64) NOT NULL,
  KEY ix_files_owner_resource (owner_id, resource_type, resource_id, module, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS upload_sessions (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
  file_id VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL,
  payload JSON NOT NULL,
  created_at VARCHAR(64) NOT NULL,
  updated_at VARCHAR(64) NOT NULL,
  KEY ix_upload_sessions_file (file_id, status),
  CONSTRAINT fk_upload_sessions_file FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS agents (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  kind VARCHAR(64) NOT NULL,
  model_provider_id VARCHAR(64) NOT NULL DEFAULT '',
  status VARCHAR(32) NOT NULL,
  payload JSON NOT NULL,
  created_at VARCHAR(64) NOT NULL,
  updated_at VARCHAR(64) NOT NULL,
  UNIQUE KEY ux_agents_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS skills (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  version VARCHAR(64) NOT NULL,
  runtime VARCHAR(128) NOT NULL,
  package_file_id VARCHAR(64) NOT NULL DEFAULT '',
  status VARCHAR(32) NOT NULL,
  payload JSON NOT NULL,
  created_at VARCHAR(64) NOT NULL,
  updated_at VARCHAR(64) NOT NULL,
  UNIQUE KEY ux_skills_name_version (name, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS agent_skills (
  agent_id VARCHAR(64) NOT NULL,
  skill_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (agent_id, skill_id),
  CONSTRAINT fk_agent_skills_agent FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE,
  CONSTRAINT fk_agent_skills_skill FOREIGN KEY (skill_id) REFERENCES skills(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS model_providers (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
  provider VARCHAR(64) NOT NULL,
  name VARCHAR(255) NOT NULL,
  credential_ref_id VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL,
  payload JSON NOT NULL,
  created_at VARCHAR(64) NOT NULL,
  updated_at VARCHAR(64) NOT NULL,
  UNIQUE KEY ux_model_providers_name (name),
  CONSTRAINT fk_model_providers_credential FOREIGN KEY (credential_ref_id) REFERENCES credentials(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS workflows (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  project_id VARCHAR(64) NOT NULL DEFAULT '',
  active_version_id VARCHAR(64) NOT NULL DEFAULT '',
  status VARCHAR(32) NOT NULL,
  payload JSON NOT NULL,
  created_at VARCHAR(64) NOT NULL,
  updated_at VARCHAR(64) NOT NULL,
  UNIQUE KEY ux_workflows_name (name),
  KEY ix_workflows_project (project_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS workflow_versions (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
  workflow_id VARCHAR(64) NOT NULL,
  version VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL,
  payload JSON NOT NULL,
  created_at VARCHAR(64) NOT NULL,
  updated_at VARCHAR(64) NOT NULL,
  UNIQUE KEY ux_workflow_versions_workflow_version (workflow_id, version),
  CONSTRAINT fk_workflow_versions_workflow FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS workflow_runs (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
  workflow_id VARCHAR(64) NOT NULL,
  workflow_version_id VARCHAR(64) NOT NULL,
  trigger_type VARCHAR(32) NOT NULL,
  status VARCHAR(32) NOT NULL,
  payload JSON NOT NULL,
  created_at VARCHAR(64) NOT NULL,
  updated_at VARCHAR(64) NOT NULL,
  KEY ix_workflow_runs_workflow (workflow_id, status, created_at),
  CONSTRAINT fk_workflow_runs_workflow FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE,
  CONSTRAINT fk_workflow_runs_version FOREIGN KEY (workflow_version_id) REFERENCES workflow_versions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS workflow_step_runs (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
  workflow_run_id VARCHAR(64) NOT NULL,
  workflow_id VARCHAR(64) NOT NULL,
  workflow_version_id VARCHAR(64) NOT NULL,
  node_id VARCHAR(128) NOT NULL,
  step_type VARCHAR(32) NOT NULL,
  sequence INT UNSIGNED NOT NULL,
  status VARCHAR(32) NOT NULL,
  predecessor_node_ids JSON NOT NULL,
  payload JSON NOT NULL,
  created_at VARCHAR(64) NOT NULL,
  updated_at VARCHAR(64) NOT NULL,
  KEY ix_workflow_step_runs_run_sequence (workflow_run_id, sequence),
  CONSTRAINT fk_workflow_step_runs_run FOREIGN KEY (workflow_run_id) REFERENCES workflow_runs(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS vcs_operations (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
  provider VARCHAR(32) NOT NULL,
  profile_id VARCHAR(64) NOT NULL,
  repository_id VARCHAR(255) NOT NULL,
  operation_type VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL,
  payload JSON NOT NULL,
  created_at VARCHAR(64) NOT NULL,
  updated_at VARCHAR(64) NOT NULL,
  KEY ix_vcs_operations_profile_repo (profile_id, repository_id, created_at),
  CONSTRAINT fk_vcs_operations_profile FOREIGN KEY (profile_id) REFERENCES gitlab_profiles(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS vcs_webhook_events (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
  provider VARCHAR(32) NOT NULL,
  profile_id VARCHAR(64) NOT NULL,
  repository_id VARCHAR(255) NOT NULL DEFAULT '',
  event_type VARCHAR(128) NOT NULL,
  status VARCHAR(32) NOT NULL,
  payload JSON NOT NULL,
  created_at VARCHAR(64) NOT NULL,
  updated_at VARCHAR(64) NOT NULL,
  KEY ix_vcs_webhook_events_profile (profile_id, event_type, created_at),
  CONSTRAINT fk_vcs_webhook_events_profile FOREIGN KEY (profile_id) REFERENCES gitlab_profiles(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS test_cases (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
  project_id VARCHAR(64) NOT NULL,
  name VARCHAR(255) NOT NULL,
  case_type VARCHAR(32) NOT NULL,
  status VARCHAR(32) NOT NULL,
  payload JSON NOT NULL,
  created_at VARCHAR(64) NOT NULL,
  updated_at VARCHAR(64) NOT NULL,
  KEY ix_test_cases_project (project_id, status),
  CONSTRAINT fk_test_cases_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS test_suites (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
  project_id VARCHAR(64) NOT NULL,
  name VARCHAR(255) NOT NULL,
  status VARCHAR(32) NOT NULL,
  payload JSON NOT NULL,
  created_at VARCHAR(64) NOT NULL,
  updated_at VARCHAR(64) NOT NULL,
  KEY ix_test_suites_project (project_id, status),
  CONSTRAINT fk_test_suites_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS test_suite_cases (
  suite_id VARCHAR(64) NOT NULL,
  case_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (suite_id, case_id),
  CONSTRAINT fk_test_suite_cases_suite FOREIGN KEY (suite_id) REFERENCES test_suites(id) ON DELETE CASCADE,
  CONSTRAINT fk_test_suite_cases_case FOREIGN KEY (case_id) REFERENCES test_cases(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS test_runs (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
  project_id VARCHAR(64) NOT NULL,
  suite_id VARCHAR(64) NOT NULL,
  environment_id VARCHAR(64) NOT NULL DEFAULT '',
  status VARCHAR(32) NOT NULL,
  payload JSON NOT NULL,
  created_at VARCHAR(64) NOT NULL,
  updated_at VARCHAR(64) NOT NULL,
  KEY ix_test_runs_project (project_id, status, created_at),
  CONSTRAINT fk_test_runs_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
  CONSTRAINT fk_test_runs_suite FOREIGN KEY (suite_id) REFERENCES test_suites(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS reports (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
  project_id VARCHAR(64) NOT NULL,
  report_type VARCHAR(32) NOT NULL,
  test_run_id VARCHAR(64) NOT NULL DEFAULT '',
  status VARCHAR(32) NOT NULL,
  payload JSON NOT NULL,
  created_at VARCHAR(64) NOT NULL,
  updated_at VARCHAR(64) NOT NULL,
  KEY ix_reports_project (project_id, report_type, status),
  CONSTRAINT fk_reports_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS quality_gates (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
  project_id VARCHAR(64) NOT NULL,
  last_report_id VARCHAR(64) NOT NULL DEFAULT '',
  status VARCHAR(32) NOT NULL,
  payload JSON NOT NULL,
  created_at VARCHAR(64) NOT NULL,
  updated_at VARCHAR(64) NOT NULL,
  KEY ix_quality_gates_project (project_id, status),
  CONSTRAINT fk_quality_gates_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS audit_events (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
  actor_id VARCHAR(64) NOT NULL,
  action VARCHAR(128) NOT NULL,
  resource_type VARCHAR(64) NOT NULL,
  resource_id VARCHAR(64) NOT NULL,
  occurred_at VARCHAR(64) NOT NULL,
  metadata JSON NOT NULL,
  payload JSON NOT NULL,
  KEY ix_audit_events_resource (resource_type, resource_id, occurred_at),
  KEY ix_audit_events_actor (actor_id, occurred_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
