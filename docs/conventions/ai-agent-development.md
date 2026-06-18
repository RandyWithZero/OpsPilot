# AI Agent Development Conventions

AI agents should make small, reviewable changes that preserve the current project boundaries.

## Working Rules

- Read the issue, latest comments, metadata, and relevant code before editing.
- Keep unrelated refactors out of the diff.
- Prefer existing scripts and conventions over introducing new tools.
- Add or update tests when behavior changes.
- Record boundary-changing decisions in an ADR.
- Never commit secrets, raw credentials, bearer tokens, production DSNs, or unredacted prompt/tool traces.

## AI Feature Rules

- Define input and output contracts before wiring an AI provider.
- Treat model output as untrusted until parsed, validated, and policy checked.
- Keep tool permissions narrow and auditable.
- Store trace metadata only after redacting sensitive data.
- Version prompts when behavior changes materially.
- Add deterministic fixtures or evals for important AI workflows.

## PR Notes

Every PR should include scope, validation commands, risk notes, rollback notes when operational behavior changes, and screenshots for UI changes.
