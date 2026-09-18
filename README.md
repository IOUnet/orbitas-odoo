# Orbitas Odoo Connector

Odoo 19 addon that connects Accounting to the Orbitas cross-ERP clearing network.

The addon is intentionally an **ERP adapter**, not the clearing engine. It:

- links an Odoo company to an Orbitas Participant Passport;
- maps posted customer invoices and vendor bills into normalized Orbitas obligations;
- keeps a durable Invoice ↔ Obligation binding;
- exports changes through an idempotent outbox, never from accounting CRUD-time network calls;
- receives clearing proposals and settlement instructions through an HMAC-authenticated webhook;
- lets Odoo users approve or reject clearing proposals;
- keeps Orbitas settlement state separate from Odoo accounting state until a real accounting workflow/reconciliation confirms discharge.

## Target

- Odoo 19.x
- Python addon installation (Odoo.sh or on-premise/custom server deployment)

## Repository layout

```text
orbitas_connector/   Odoo addon
docs/                connector/API notes
tools/               lightweight static checks
.github/workflows/   repository quality checks
```

## Installation

Add this repository to the Odoo addons path, update Apps, then install **Orbitas Connector**.

The addon depends on `account` and `base_setup`.

## First setup

1. Open **Orbitas → Configuration → Backends**.
2. Create a backend for the company.
3. Configure the Orbitas gateway base URL and API token.
4. Configure the outbound endpoint templates expected by your Orbitas gateway.
5. Set a webhook secret and copy the generated webhook URL into the gateway.
6. Register/link the company Participant Passport.
7. Optionally enable automatic export of newly posted invoices and bills.

## Accounting safety

A remote clearing proposal or settlement instruction does **not** directly set an invoice to paid and does not write `amount_residual` / `payment_state`. The accounting discharge step must be performed by an explicit, supported payment/reconciliation workflow.

## API contract

The transport contract is deliberately configurable because the canonical Orbitas gateway API is maintained outside this repository. See [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md).

## Development

Lightweight repository checks:

```bash
python -m compileall -q orbitas_connector
python tools/check_xml.py
```

Odoo runtime tests are in `orbitas_connector/tests/` and should be executed in an Odoo 19 test database, e.g. with the module test tags selected by your Odoo CI environment.

## Status

This is the initial MVP implementation of the Odoo reference connector. It implements the product flow:

```text
Invoice/Bill
  → Orbitas obligation
  → candidate clearing proposal
  → Approve / Reject
  → settlement instruction
  → payment evidence / explicit accounting workflow
  → reconciliation
```
