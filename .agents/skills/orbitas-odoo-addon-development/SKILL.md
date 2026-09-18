---
name: orbitas-odoo-addon-development
version: "2.0.0"
description: Build, modify, review, test, debug, secure, or upgrade Odoo addons and ERP connectors for Orbitas. Use for Odoo Python/XML/JS changes, account.move integration, multi-company/security, webhooks, outbox/idempotency, Participant Passport, obligations, clearing proposals, settlement instructions, and PR/code review. Do not use for ordinary Odoo end-user help, accounting advice without code, or unrelated Python/web development.
license: Internal project guidance; upstream source references retain their own licenses.
---

# Orbitas Odoo Addon Development

Use this skill as the **operational workflow** for ChatGPT/Codex when working on Odoo code, especially `IOUnet/orbitas-odoo` and related Orbitas ERP adapters.

The detailed Odoo engineering rules are in [`references/ODOO_ENGINEERING.md`](references/ODOO_ENGINEERING.md). Load that reference when the task touches implementation details, security, accounting semantics, performance, testing, frontend, controllers, migrations, or release readiness. Load [`references/ORBITAS_CONNECTOR_PROFILE.md`](references/ORBITAS_CONNECTOR_PROFILE.md) whenever the task touches Orbitas domain behavior.

## 1. Trigger and scope

Invoke this skill when the user asks to:

- create or change an Odoo addon/module;
- modify Python models, XML views/data/security, controllers, Owl/JS, migrations, tests, or manifest files;
- integrate Odoo with Orbitas or another external service;
- map invoices/bills to Orbitas obligations;
- implement Participant Passport, clearing proposals, consent, settlement instructions, webhook processing, bindings, retries, or outbox behavior;
- review an Odoo PR for correctness/security/performance;
- port an addon to another Odoo major;
- diagnose a failing Odoo install/update/test caused by addon code.

Do **not** invoke this skill for:

- ordinary Odoo UI/end-user questions;
- accounting/legal advice with no software change;
- unrelated backend/frontend development;
- generic blockchain work with no Odoo integration boundary.

## 2. ChatGPT/Codex operating contract

Work as a repository-aware coding agent, not as a code generator detached from the project.

Before editing:

1. Read all applicable `AGENTS.md` / `AGENTS.override.md` instructions from repository root to the working directory.
2. Inspect the current repository tree, `README`, addon manifest, relevant docs/TRDs, existing tests, and nearby implementation before proposing a design.
3. Detect the actual Odoo major from manifest/branch/repository context. **Odoo 19.x is the default only when the repository confirms it.**
4. Reuse existing project abstractions, names, DTOs, test helpers, and security groups before introducing new ones.
5. If behavior depends on an external/current API, verify the exact current contract from authoritative docs or repository sources rather than guessing.

While editing:

- make the smallest coherent change that satisfies the task;
- preserve existing public contracts unless change is explicitly requested;
- keep business logic in testable model/service methods, not controllers/XML;
- avoid speculative framework APIs;
- do not add production dependencies unless they are necessary and justified;
- never introduce secrets or credentials into the repository;
- never hide failing behavior with broad `sudo()`, exception swallowing, manual commits, or direct SQL accounting updates.

After editing:

1. Run the repository's documented validation commands.
2. Run the narrowest relevant Odoo tests available, then broader tests when practical.
3. Inspect the diff for accidental unrelated changes.
4. Report what changed, what was validated, and what could not be validated in the current environment.
5. Do not claim runtime compatibility from static lint alone.

## 3. Progressive-disclosure rule

Keep the main skill lightweight. Load supporting references only when needed:

- `references/ODOO_ENGINEERING.md` — full Odoo engineering/security/testing rules;
- `references/ORBITAS_CONNECTOR_PROFILE.md` — Orbitas-specific domain invariants and current connector architecture;
- `references/SOURCES.md` — authoritative source list and version/review dates.

When a task is narrow, do not flood the working context with every reference. When risk is high (Accounting, security, multi-company, migrations, webhooks), load the relevant references before changing code.

## 4. Default repository workflow

For a code-change task, follow this sequence unless repository instructions override it:

```text
UNDERSTAND
  ↓
inspect AGENTS.md + repo + manifest + docs + nearby tests
  ↓
CLASSIFY RISK
  ↓
accounting / security / multicompany / migration / integration / UI
  ↓
DESIGN
  ↓
small extension-first change; preserve Orbitas/Odoo boundary
  ↓
IMPLEMENT
  ↓
models/services → security → views/controllers → tests/docs
  ↓
VALIDATE
  ↓
syntax/lint/XML → Odoo install/update/tests → failure-path checks
  ↓
REVIEW DIFF
  ↓
report exact validation + remaining uncertainty
```

Do not start by rewriting a whole file or creating a parallel architecture when the repository already has an extension point.

## 5. Risk classifier

Treat these areas as **high risk** and load the detailed reference before editing:

### Accounting

Anything touching `account.move`, payments, reconciliation, residual amounts, credit notes, posting, journal entries, or settlement semantics.

### Security

ACLs, record rules, public controllers, RPC-callable methods, `sudo()`, secret fields, webhook authentication.

### Multi-company

Connector backends, bindings, outbox/inbound events, company-scoped configuration, `with_company`, `check_company`, company record rules.

### External side effects

HTTP/API/blockchain calls, webhooks, cron/queues, retries, idempotency, crash recovery.

### Persistent schema/migrations

Model/field/XML-ID renames, selection-state meaning, constraints, stored compute changes, data migrations.

For high-risk changes, tests are part of the implementation, not an optional follow-up.

## 6. Odoo framework invariants

The following are non-negotiable unless the user explicitly approves an architecture exception:

- extension-first; do not fork/copy Odoo core for normal customization;
- ORM-first; raw SQL is exceptional and reviewed;
- batch-safe recordset methods;
- no manual `cr.commit()` / `cr.rollback()` in normal addon code;
- no network/blockchain side effects from compute/onchange/constraint or normal CRUD transaction paths;
- every persistent model has explicit ACL/record-rule design;
- multi-company isolation is explicit and tested;
- `sudo()` is minimal, justified, and bounded;
- controllers are thin and validate untrusted inputs;
- no direct writes to derived accounting fields such as `amount_residual` or `payment_state`;
- no dynamic runtime package installation;
- user-facing strings are translatable;
- migrations preserve data and stable XML IDs.

For exact patterns and examples, load `references/ODOO_ENGINEERING.md`.

## 7. Orbitas architectural invariants

For Orbitas work, treat Odoo as an **ERP adapter and user interaction surface**, not as the clearing engine or settlement authority.

Keep this boundary:

```text
Odoo accounting data
    ↓
adapter eligibility + mapping
    ↓
normalized Orbitas domain payload
    ↓
durable outbox / authenticated inbound events
    ↓
Orbitas Core / indexer / settlement layer
```

Mandatory semantics:

1. **Invoice/Bill → Obligation** is a normalized mapping, not serialization of Odoo internals.
2. Keep a stable source binding: Odoo instance + company + model + record id → remote Orbitas id.
3. Remote operations are idempotent and retry-safe.
4. A clearing search returns **candidates**, not automatic settlement.
5. Approval/rejection is an explicit consent action when policy requires it.
6. A settlement instruction is not automatically proof of accounting discharge or novation.
7. Odoo becomes paid/reconciled only through an explicit supported accounting workflow.
8. Orbitas-specific statuses live in connector models and must not overwrite accounting truth.
9. Odoo/QBO/1C-specific objects must not leak into the cross-ERP clearing core.

Load `references/ORBITAS_CONNECTOR_PROFILE.md` for the current module/profile.

## 8. Repository inspection checklist

Before implementation, locate and read as applicable:

- `AGENTS.md` / `AGENTS.override.md`;
- `README.md`;
- `__manifest__.py`;
- `models/__init__.py`, model files being extended;
- security XML and `ir.model.access.csv`;
- inherited views/actions/menus;
- controller/webhook code;
- tests for the affected model/workflow;
- migration directories;
- CI/pre-commit config;
- Orbitas API/domain documentation such as `docs/API_CONTRACT.md` or TRDs.

Do not infer a missing contract from filenames alone. Search the repository first.

## 9. Change-design template

Before a non-trivial edit, internally resolve these questions:

- What is the source of truth: Odoo, Orbitas Core, or an inbound event?
- What Odoo business state is being observed versus mutated?
- What is the stable identity/idempotency key?
- Which company owns the record?
- Which user/group is allowed to see or trigger it?
- Can a retry duplicate the remote effect?
- What happens if the remote side accepts but Odoo crashes before recording success?
- What happens for partial payment, cancellation, reversal, refund, multi-currency, and multi-company?
- Is this a candidate/instruction/status, or actual accounting evidence?
- What exact tests prove the invariant?

If these questions expose an architectural ambiguity, prefer an explicit technical TODO/contract boundary over inventing behavior.

## 10. Edit strategy for Codex/ChatGPT

Prefer edits in this order:

1. domain/model/service behavior;
2. security and company scoping;
3. durable integration mechanics (binding/outbox/inbound processing);
4. thin controller/API route;
5. views/actions/menu exposure;
6. tests;
7. docs/migrations/CI.

When modifying a method, inspect callers and tests first. When adding a field/model, search for similarly named existing concepts. When adding a state, inspect all selections, views, record rules, cron logic, and tests that depend on state transitions.

Do not create duplicate “v2” models, services, or helpers solely to avoid understanding existing code.

## 11. Git and remote-action discipline

For Codex/ChatGPT working in a Git repository:

- do not rewrite unrelated user changes;
- do not use destructive Git operations (`reset --hard`, force-push, mass checkout) unless explicitly requested;
- do not commit generated secrets, local DBs, `.env`, caches, or credentials;
- keep commits logically scoped when the user asks for commits;
- create/push branches, open PRs, merge, tag, release, or modify CI secrets only when the user requests or clearly authorizes that remote action;
- before PR/merge, run required checks and include known validation gaps in the PR description.

If another agent/user changed a file concurrently, re-read it before overwriting.

## 12. Validation matrix

Use repository-native commands first. For the current `orbitas-odoo` reference repository, typical static checks are:

```bash
python -m compileall -q orbitas_connector
python tools/check_xml.py
ruff check orbitas_connector tools
```

When an Odoo runtime is available, also validate:

- clean install of the addon;
- module update (`-u`) on a populated test DB;
- relevant tagged tests;
- two-company security isolation;
- posting/export mapping;
- outbox idempotency/retry/dead-letter behavior;
- webhook signature/replay behavior;
- clearing approve/reject lifecycle;
- settlement instruction without shortcutting Odoo reconciliation.

For Accounting changes, static checks are never sufficient proof.

## 13. Failure-path requirements

Integration code is incomplete until important failure paths are covered.

At minimum consider:

- timeout / connection reset;
- 4xx permanent failure;
- 429 / 5xx retryable failure;
- duplicate outbound request;
- duplicate/replayed webhook;
- stale webhook timestamp;
- remote-accepted/local-crash ambiguity;
- max retries / dead letter;
- source edited after export;
- record cancelled or fully discharged after export;
- access from a user/company that should not see the record.

Do not convert unknown failures into success or silently swallow them.

## 14. Review mode

When the user asks for a review, prioritize findings over summary.

Review in this order:

1. accounting/data corruption risk;
2. security / cross-company leakage;
3. external-side-effect/idempotency bugs;
4. broken Odoo API contracts / upgrade hazards;
5. missing failure-path tests;
6. performance/N+1 issues;
7. maintainability/style.

For each finding, state:

- severity;
- concrete file/behavior;
- why it matters in Odoo/Orbitas;
- minimal corrective action;
- test that should prevent regression.

Do not invent a defect when evidence is insufficient; mark uncertainty and inspect more context.

## 15. Debug mode

When debugging a failing Odoo module:

1. capture the exact traceback/test failure;
2. identify the first project-owned frame, not just the last exception line;
3. verify target Odoo version/API before changing syntax;
4. inspect manifest load order and missing XML IDs for install errors;
5. inspect ACL/record rules/company context for AccessErrors;
6. inspect ORM batch/singleton assumptions for `Expected singleton`;
7. inspect view inheritance anchors for parse/XPath failures;
8. inspect transaction/outbox timing for integration inconsistencies;
9. add a regression test before or with the fix.

Avoid “fixes” that disable the test, broaden `sudo()`, or bypass accounting state machines.

## 16. Migration/upgrade mode

When upgrading Odoo major or persistent schema:

- identify every Odoo API/view/frontend change against the exact target major;
- install cleanly on target major;
- run module update on migrated data;
- add migration scripts for model/field/XML-ID/selection meaning changes;
- preserve bindings and remote IDs;
- do not reset connector state merely to make migration easier;
- explicitly test queued/retry/dead outbox records across migration.

Load the migration sections of `references/ODOO_ENGINEERING.md` before implementation.

## 17. Completion report format

End a coding task with a compact report containing:

- **Changed:** files/behaviors actually modified;
- **Validated:** exact commands/tests that passed;
- **Not validated:** runtime/integration checks unavailable in the environment;
- **Risk/next step:** only concrete remaining risks, not generic boilerplate.

Never say “fully tested” if only lint/static checks ran.

## 18. Repository integration

For Codex, place this skill in the repository so it is auto-discoverable:

```text
<repo>/.agents/skills/orbitas-odoo-addon-development/SKILL.md
<repo>/.agents/skills/orbitas-odoo-addon-development/references/...
<repo>/.agents/skills/orbitas-odoo-addon-development/agents/openai.yaml
```

Use the root `AGENTS.md` for **short repository-wide invariants and commands**, not for duplicating the entire skill.

The skill should contain reusable workflow/domain knowledge; `AGENTS.md` should contain repository-specific instructions. Keep these layers complementary rather than repetitive.
