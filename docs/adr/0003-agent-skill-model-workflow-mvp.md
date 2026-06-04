# ADR 0003: Agent, Skill, Model Provider, and Workflow MVP

## Status

Accepted

## Context

OpsPilot needs agent participation in operations, skill management, model API key/provider configuration, and workflow definitions. The current foundation service is still a local MVP with in-memory persistence and safe credential references from ADR 0002.

## Decision

Add a bounded backend/API slice to the foundation service:

- Agent registry tracks agent identity, kind, capabilities, linked skills, and optional model provider.
- Skill catalog tracks skill name, version, runtime, capabilities, status, and optional package file reference.
- Model providers reference existing `model_provider` credentials instead of accepting raw model API keys directly.
- Workflow definitions are versioned. Each version contains simple node and edge arrays with validation for unique node IDs and edge references to existing nodes.

All create/update/delete/version actions emit audit events. The models remain intentionally minimal so future dedicated services can preserve these contracts while moving persistence to MySQL.

## Consequences

The platform can now model the first agent-assisted workflow surface locally without introducing secret leakage or broad orchestration runtime behavior. Real workflow execution, queueing, policy checks, and model invocation remain future milestones.
