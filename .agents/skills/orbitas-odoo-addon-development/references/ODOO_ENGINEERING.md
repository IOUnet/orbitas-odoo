# Odoo Engineering Reference for Orbitas

Reviewed: 2026-09-18  
Baseline: Odoo 19.x unless the repository manifest/branch states otherwise.

This reference contains the detailed engineering rules used by the repository skill. It is intentionally stricter than generic Odoo examples because this addon touches Accounting, external side effects, webhooks and multi-company data.

## 1. Version discipline

- Detect the target Odoo major from the current branch and `__manifest__.py`.
- Use documentation and APIs for that exact major.
- Do not copy examples from another Odoo major without checking compatibility.
- Prefer explicit ports between majors over dense compatibility branches.
- A Python addon requires Odoo.sh, on-premise or another deployment model that supports custom server modules.

## 2. Extension-first

Prefer Odoo extension points over copied core code:

1. Python `_inherit`;
2. XML view inheritance;
3. frontend registries/services/components;
4. documented controller/API extension points;
5. JS `patch()` only when no stable extension point exists;
6. core fork only by explicit architecture decision.

Do not copy entire standard models/views/controllers for a small behavior change.

## 3. Module structure

Keep conventional locations:

```text
orbitas_connector/
├── __init__.py
├── __manifest__.py
├── models/
├── controllers/
├── security/
├── data/
├── views/
├── tests/
├── static/src/
└── migrations/
```

Business logic belongs in model/service methods, not XML or controllers.

## 4. Manifest rules

- Declare only real `depends`.
- Load groups/security before views/actions that depend on them.
- Declare frontend assets through the manifest.
- Never install Python packages dynamically at runtime.
- Keep deployment dependencies explicit and reproducible.
- Preserve a deliberate license and module version.

## 5. Naming

- Models: singular dot notation, e.g. `orbitas.obligation.binding`.
- Many2one: `*_id`.
- One2many/Many2many: `*_ids`.
- Compute: `_compute_*`.
- Onchange: `_onchange_*`.
- Constraint: `_check_*`.
- Public user actions: `action_*`.
- Extension hooks: `_prepare_*`, `_get_*`, `_validate_*`, `_sync_*`.
- Preserve released XML IDs; migrate deliberate renames.

## 6. ORM-first and batch safety

Use recordsets and the ORM by default.

- Multi-record methods should stay multi-record unless the contract is genuinely singleton.
- Use `ensure_one()` only for true singleton actions.
- Preserve batch creation with `@api.model_create_multi`.
- Use `Command` helpers for x2many operations.
- Use `with_context()` and `with_company()` deliberately.
- Call `super()` and preserve standard method contracts.

Avoid a `search()`, `search_count()` or remote call inside a loop when the operation can be batched.

## 7. Raw SQL

Raw SQL is exceptional.

If required:

- parameterize all values;
- flush relevant ORM state before SQL reads/writes;
- invalidate the narrowest relevant caches after SQL writes;
- document why ORM was insufficient;
- test access/security/consistency.

Never use SQL to bypass Accounting state machines, reconciliation, ACLs, computed fields or company rules.

## 8. Transaction ownership

Do not call `cr.commit()` or `cr.rollback()` in normal addon code.

Odoo owns RPC/test/cron transaction boundaries. Manual commits create partial state and make rollback behavior unreliable.

## 9. External side effects: durable outbox

Do not execute irreversible remote effects inside normal:

- `create()`;
- `write()`;
- compute methods;
- constraints;
- onchange;
- accounting posting logic.

Preferred architecture:

```text
Odoo transaction
  ├─ update accounting/connector records
  └─ insert durable outbox event
        ↓ Odoo commit
cron/worker
  ├─ send to Orbitas
  ├─ record remote id / receipt
  └─ retry idempotently
```

Outbox requirements:

- durable state such as pending/processing/done/retry/dead;
- stable idempotency key;
- bounded retry count;
- backoff;
- network timeout;
- remote reference/response hash;
- safe re-entry after process crash;
- no secrets in logs.

A failed Orbitas API call should not corrupt or silently roll back core Accounting state unless synchronous rejection is an explicit product requirement.

## 10. ACLs, record rules and sensitive fields

Every persistent model requires an explicit security design:

1. `ir.model.access` for CRUD capability;
2. record rules for row scope;
3. field `groups` for sensitive fields;
4. model-level validation for business invariants.

Remember:

- ACL grants are additive;
- UI invisibility is not authorization;
- record rules must be reviewed for their composition and company scope;
- public/RPC-callable methods must not trust client-provided authority.

## 11. Minimal `sudo()`

Use `sudo()` only when the caller's authority has already been validated and only around the smallest required operation.

Never use broad `sudo().search([])` as an access-error workaround. Do not return elevated recordsets to general user code.

For every elevation ask:

- why normal ACL/rules are insufficient;
- which records/fields need elevation;
- whether company isolation is still enforced;
- which test proves no data leak.

## 12. Multi-company

Company-sensitive connector data must be explicitly scoped.

For relevant models:

- store `company_id`;
- prefer defaults based on `env.company`;
- use `_check_company_auto` and `check_company=True` where appropriate;
- use `with_company()` when evaluating company-dependent behavior;
- design record rules using authorized company sets;
- test with at least two companies and users.

Orbitas backend config, credentials, bindings, outbox, inbound events, proposals and settlement instructions must not leak across companies.

## 13. Accounting safety

Posted invoices/bills are accounting facts, not arbitrary workflow records.

- Use supported Odoo posting/payment/reconciliation methods.
- Never directly set `amount_residual`, `payment_state` or derived reconciliation fields.
- Never silently unpost/repost.
- Preserve currency, company, partner, invoice date and due date semantics.
- Treat refunds/credit notes explicitly.
- Treat partial payments explicitly.
- Remote Orbitas state must not redefine legal/accounting discharge by itself.

Connector state belongs in connector models.

## 14. Compute, onchange and constraints

- Compute methods must be batch-safe and declare complete dependencies.
- Do not perform remote IO from compute/onchange/constraint.
- Onchange is UI assistance, not the only enforcement of a business invariant.
- Constraints must be deterministic and free of irreversible side effects.

## 15. Performance

- Batch create/write operations.
- Let ORM prefetch work; avoid scalar loops that defeat it.
- Replace repeated counts/aggregations with grouped reads where appropriate.
- Use sets/dicts for correlation rather than nested record loops.
- Add indexes selectively for real lookup patterns.
- Bound cron searches and process in deterministic batches.
- Use the profiler/query counts for bulk paths.

## 16. Cron, retries and crash safety

Scheduled jobs should be:

- bounded;
- idempotent;
- resumable;
- deterministic;
- safe after worker crash.

Do not wrap thousands of external requests in one giant transaction. Prefer a durable outbox or a reviewed queue mechanism.

## 17. Views

Use inherited views and narrow anchors.

- Avoid fragile broad XPaths.
- Keep view logic presentational.
- Security groups in XML are convenience, not the security boundary.
- Surface diagnostics/status with dedicated fields/smart buttons rather than mutating Accounting truth.

## 18. Frontend / Owl

For Odoo 19 frontend work:

- use Owl and registries/services first;
- use `useService` and Odoo services for model/RPC operations;
- declare assets in the manifest;
- prefer registry/service extension over `patch()`;
- use `patch()` only when necessary and keep it deterministic.

Re-check frontend APIs against the target Odoo major before coding.

## 19. Controllers and webhooks

Controllers should be thin.

For machine webhooks:

- public route only when required;
- strong signature verification;
- timestamp tolerance;
- unique event/replay id;
- bounded payload handling;
- idempotent processing;
- no secrets in errors/logs;
- business processing delegated to models/services.

Disabling CSRF for a machine webhook is acceptable only with strong request authentication and replay defense.

## 20. External API strategy

For new external integrations against Odoo 19, prefer the current supported API patterns rather than adding new dependencies on legacy XML-RPC/JSON-RPC interfaces scheduled for future removal.

Inside the addon, use the ORM. Keep external API transport behind an adapter/interface so API changes do not spread through Accounting logic.

## 21. Secrets

Do not place credentials in:

- source control;
- XML/demo data;
- browser JS;
- chatter;
- logs.

If a secret is stored in Odoo:

- restrict read/write with groups;
- avoid rendering it to unauthorized clients;
- separate secret fields from ordinary settings;
- support rotation;
- never include it in diagnostic payloads.

## 22. Stable bindings and idempotency

Stable source identity should include:

```text
odoo_instance_id
+ company_id
+ source_model
+ source_record_id
```

A binding may store:

- source identity;
- source revision/write timestamp;
- payload hash;
- remote Orbitas id;
- last synchronized state;
- last success time;
- last error classification.

Use a DB uniqueness constraint for the source identity. Retries must not create duplicate obligations. Duplicate inbound events must not apply a settlement twice.

## 23. Orbitas adapter boundary

Target flow:

```text
Odoo accounting objects
  ↓
eligibility + mapping
  ↓
normalized Orbitas DTO
  ↓
durable outbox
  ↓
Orbitas API / clearing core / indexer / settlement layer
```

Do not pass Odoo recordsets or Odoo-specific behavior into cross-ERP core logic.

For invoice-backed obligations capture enough source evidence to reproduce mapping, including:

- Odoo instance;
- company;
- source model/id;
- invoice/bill number/reference;
- counterparty;
- move type;
- currency;
- original amount;
- outstanding/residual amount;
- invoice/due dates;
- source/accounting state;
- source revision/write date.

Eligibility is an explicit product/adapter policy; do not infer it from one field.

## 24. Inbound settlement semantics

Keep these stages distinct:

1. Orbitas instruction observed;
2. company/user consent confirmed where required;
3. payment/settlement evidence received;
4. Odoo accounting action performed;
5. Odoo reconciliation confirmed.

A settlement instruction is not automatically novation and is not automatically proof that an Odoo invoice is discharged.

## 25. Logging and observability

Use Python logging.

Useful correlation fields:

- backend id;
- company id;
- binding/outbox id;
- source model/id;
- correlation/request id;
- remote reference.

Never log credentials, private keys, full invoice documents or unnecessary PII.

Expose operational health such as:

- last successful sync;
- pending count;
- retry count;
- oldest pending event;
- last error category.

## 26. Tests

### Model tests

Use Odoo test cases for:

- mapping;
- eligibility;
- state transitions;
- idempotency;
- multi-record behavior;
- error paths.

### Security tests

Use real users/groups to prove:

- ACLs;
- record rules;
- sensitive field access;
- multi-company isolation;
- no accidental `sudo()` widening.

### Integration failure tests

Simulate:

- timeout;
- 4xx;
- 429/5xx;
- duplicate request;
- accepted-remote/local-crash ambiguity;
- retry exhaustion;
- stale source revision;
- replayed webhook.

### Accounting scenarios

Cover as applicable:

- draft vs posted;
- customer invoice vs vendor bill;
- credit note/refund;
- partial payment;
- full discharge;
- cancellation/reversal;
- multi-currency;
- multi-company;
- source edited after export.

## 27. Migration and upgrades

An Odoo-major upgrade is a migration project.

For a major upgrade:

1. clean install on the target major;
2. remove deprecated API/view/frontend usage;
3. run tests;
4. test on an upgraded copy of real data;
5. add migration scripts for schema/model/field/XML-ID/selection meaning changes;
6. rehearse the production upgrade.

Migration layout:

```text
<module>/migrations/<version>/pre-*.py
<module>/migrations/<version>/post-*.py
<module>/migrations/<version>/end-*.py
```

Preserve Orbitas bindings, remote ids and pending/retry/dead outbox state across migrations.

## 28. CI and lint

At minimum validate:

- Python syntax;
- XML syntax;
- Ruff/Python lint;
- Odoo-specific lint such as pinned `pylint-odoo` when available;
- addon clean install;
- module tests;
- update/migration test when persistent schema changed.

Treat static checks as necessary but insufficient for Accounting behavior.

## 29. Translation and dependencies

- All user-facing strings should be translatable.
- Do not translate technical identifiers.
- Keep error messages useful without revealing secrets.
- Verify third-party module compatibility, maintenance and license.
- Verify Odoo.sh/on-prem deployment constraints before adding system/Python dependencies.

## 30. Review red flags

Treat these as architecture problems, not style nits:

```python
for move in moves:
    self.env["some.model"].search([...])   # N+1
```

```python
self.env.cr.commit()                       # partial transaction
```

```python
self.sudo().search([])                     # broad security bypass
```

```python
requests.post(url, json=payload)           # inside account.move.write()
```

```python
self.env.cr.execute(
    "UPDATE account_move SET payment_state='paid' ..."
)
```

Also reject:

- secrets in XML/JS/repository/logs;
- a business invariant enforced only by onchange;
- JS patching where a registry/service extension exists;
- unbounded cron loops;
- duplicate remote objects after retry;
- settlement instructions that directly mark invoices paid.

## 31. Definition of done for Orbitas connector changes

A behavior-changing increment is ready when applicable checks pass:

- clean addon install;
- `-u` update on populated test data;
- two-company security tests;
- deterministic source → Orbitas mapping;
- repeat export is idempotent;
- network failure does not corrupt Odoo Accounting;
- retry/dead-letter behavior works;
- inbound events are replay-safe;
- accounting state changes only through supported workflows;
- relevant bulk path is query/profile bounded;
- lint and Odoo tests are green;
- migration notes/scripts exist when persistent meaning changed.

For authoritative links and review dates, see `SOURCES.md`.
