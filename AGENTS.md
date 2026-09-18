# AGENTS.md — Orbitas Odoo repository

## Repository contract

- This repository contains the Odoo 19 reference addon integrating Accounting with Orbitas.
- Before Odoo addon changes, use the repository skill at `.agents/skills/orbitas-odoo-addon-development/SKILL.md`.
- Read `README.md`, `docs/`, `orbitas_connector/__manifest__.py`, nearby models/security/views/tests, and this file before editing.
- Target the Odoo major declared by the manifest/branch. Current baseline is Odoo 19.x.
- Prefer the smallest coherent change that reuses existing models, bindings, outbox, security groups and tests.

## Architecture invariants

- Odoo is an ERP adapter and user interaction surface, not the Orbitas clearing engine.
- Normalize Odoo records into Orbitas domain payloads; do not leak Odoo-specific objects into Orbitas Core.
- External side effects go through the durable outbox/worker path, not normal accounting CRUD/compute/constraint/onchange.
- Keep Orbitas proposal/settlement state separate from Odoo accounting truth.
- A settlement instruction does not itself prove accounting discharge or novation.
- Never write derived accounting fields such as `amount_residual` or `payment_state` directly.
- Never use broad `sudo()` to bypass security or multi-company rules.
- No manual `cr.commit()` / `cr.rollback()` in normal addon code.
- Keep webhook controllers thin, authenticated, replay-safe and idempotent.
- Preserve stable Invoice/Bill ↔ Orbitas Obligation bindings and idempotency keys across retries.

## Current addon

- Addon: `orbitas_connector`
- Odoo baseline: 19.x
- API contract: `docs/API_CONTRACT.md`
- Skill: `.agents/skills/orbitas-odoo-addon-development/`

## Required validation

Run repository-native checks at minimum:

```bash
python -m compileall -q orbitas_connector
python tools/check_xml.py
ruff check orbitas_connector tools
```

When an Odoo runtime is available, also run relevant addon tests and verify clean install/update for behavior-changing changes.

For high-risk changes touching Accounting, security, multi-company, webhooks, retries, migrations or settlement semantics, static checks alone are not sufficient.

## Testing expectations

Add or update tests for applicable behavior, especially:

- customer invoice vs vendor bill mapping;
- multi-company isolation;
- idempotent export/retry;
- timeout/4xx/429/5xx behavior;
- webhook replay/timestamp/signature validation;
- clearing approve/reject authorization and lifecycle;
- settlement instructions without shortcutting Odoo reconciliation.

## Git discipline

- Do not overwrite unrelated user changes.
- Do not use destructive Git commands unless explicitly requested.
- Do not commit secrets, local databases, caches or environment files.
- Re-read files before overwriting if another actor may have changed them.
- Do not push, merge, tag, release, or modify repository secrets unless the user explicitly requests that remote action.

## Completion report

State:

- **Changed:** files and behavior actually modified;
- **Validated:** exact tests/checks run and their result;
- **Not validated:** runtime/integration checks unavailable in the environment;
- **Risk/next step:** only concrete remaining risks or follow-ups.

Never claim runtime compatibility from lint/static checks alone.
