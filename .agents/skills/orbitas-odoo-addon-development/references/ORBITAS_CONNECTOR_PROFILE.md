# Orbitas Odoo Connector Profile

Reviewed: 2026-09-18

This reference captures the current project-specific interpretation for the Orbitas Odoo connector. It supplements, and does not replace, the general Odoo engineering rules.

## Role of the addon

The Odoo addon is the **reference ERP adapter** for Orbitas. It should expose Odoo accounting data and user consent to Orbitas while keeping the cross-ERP clearing core independent from Odoo-specific models.

Current product flow:

```text
Invoice / Vendor Bill
  → normalized Orbitas obligation
  → candidate clearing proposal
  → explicit Approve / Reject when required
  → settlement instruction
  → payment/evidence through supported process
  → Odoo accounting reconciliation
```

## Current reference module

Repository: `IOUnet/orbitas-odoo`

Primary addon: `orbitas_connector`

Target baseline: Odoo 19.x unless the repository branch/manifest says otherwise.

## Current functional responsibilities

The connector should provide these responsibilities while preserving separation from Orbitas Core:

1. **Backend/company configuration**
   - bind an Odoo company to an Orbitas backend;
   - store/link the Participant Passport identifier;
   - scope credentials/configuration by company;
   - expose connectivity/operational health without leaking secrets.

2. **Invoice/bill mapping**
   - map posted customer invoices and vendor bills into normalized Orbitas obligations;
   - customer invoice: partner is debtor, Odoo company is creditor;
   - vendor bill: Odoo company is debtor, partner is creditor;
   - include source identity, currency, original/outstanding amount, dates, document state, and source revision as needed.

3. **Stable binding**
   - stable source identity uses Odoo instance + company + model + record id;
   - store remote obligation id separately;
   - retries must reuse the same identity and must not create duplicate obligations.

4. **Durable outbox**
   - no remote HTTP/blockchain action inside normal accounting CRUD/compute/constraint/onchange;
   - durable states should distinguish pending/processing/done/retry/dead or equivalent;
   - use stable idempotency keys and bounded retries/backoff.

5. **Clearing discovery**
   - Odoo may request candidate clearing paths;
   - candidates are proposals, not final accounting action;
   - graph/path discovery remains outside Odoo.

6. **Consent**
   - display a clearing proposal to authorized users;
   - approve/reject is explicit and server-authorized;
   - UI visibility alone is not authorization.

7. **Settlement instructions**
   - receive/store authenticated inbound settlement instructions;
   - keep Orbitas settlement state separate from Odoo payment/reconciliation state;
   - do not set `amount_residual`, `payment_state`, journal entries, or reconciliation by shortcut.

8. **Inbound events**
   - authenticate webhook requests;
   - check timestamp/replay identity;
   - process idempotently;
   - keep controllers thin and processing logic testable in models/services.

9. **Multi-company isolation**
   - backend, binding, outbox, inbound event, clearing proposal, settlement instruction and secret configuration must be company-scoped;
   - include record-rule/security tests with at least two companies.

## Accounting invariants

- A settlement instruction is **not** automatic novation.
- “Orbitas settled” is **not** automatically “Odoo invoice paid”.
- Accounting discharge is proven only by a supported Odoo accounting workflow and reconciliation/evidence appropriate to the implementation.
- Partial payments and credit notes must be modeled explicitly rather than inferred from a single status.
- Cancellation and full discharge are different lifecycle events.

## Orbitas Core boundary

Do not put into Odoo:

- global invoice-graph traversal;
- authoritative cross-ERP clearing logic;
- blockchain settlement authority;
- global indexing/query projection responsibilities;
- generic cross-ERP domain types polluted with Odoo recordsets/model names beyond source metadata.

The adapter may translate Odoo data into a normalized DTO and present remote decisions/states to users.

## Recommended tests for connector changes

Depending on the feature, cover:

- customer invoice direction;
- vendor bill direction;
- posted vs draft;
- partial payment/residual change;
- full discharge/close;
- cancellation/reversal;
- credit note/refund behavior;
- multi-currency;
- multi-company access isolation;
- repeated export/idempotency;
- timeout/429/5xx retry;
- permanent 4xx dead-letter behavior;
- remote accepted + local crash ambiguity;
- webhook replay and stale timestamp;
- approve/reject permission and state transition;
- settlement instruction without accounting shortcut.
