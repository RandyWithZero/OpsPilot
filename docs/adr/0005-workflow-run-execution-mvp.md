# ADR 0005: Workflow Run Execution MVP

## Status

Accepted

## Context

Workflow definitions and versions can now be created from the console, but the backend did not yet represent execution state. The first execution slice needs to stay local-testable and avoid coupling the foundation service to an agent runtime or queue.

## Decision

Add workflow run and workflow step run records inside the foundation service:

- A run is created from the workflow active version by default and stores the workflow/version IDs as an execution snapshot reference.
- Step runs are derived from saved version nodes and edges using stable topological ordering.
- Each step run stores immutable predecessor node IDs at run creation so later workflow-version edits cannot change the execution gating for an existing run.
- Manual start moves a created run to running and marks trigger steps completed.
- Agent, manual, and result step runs support explicit status transitions and output/error capture.
- Run status rolls up from step state for completed and failed terminal outcomes.
- Audit events record run creation, manual start, and step updates with IDs/status metadata only.

## Consequences

This provides an API contract for the console and later runtime workers without starting background execution. Future agent dispatch, retries, queues, and durable persistence can attach behind the current run/step records.
