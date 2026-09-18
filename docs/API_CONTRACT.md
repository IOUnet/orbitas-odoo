# Orbitas gateway contract used by the Odoo connector

The addon keeps the HTTP transport behind `orbitas.backend`, and endpoint paths are configurable per backend. This avoids coupling the accounting addon to an unstable gateway URL layout.

## Outbound authentication

Requests use:

```http
Authorization: Bearer <api token>
Content-Type: application/json
Idempotency-Key: <stable sha256 key>
```

Every mutating outbound operation must be idempotent on the Orbitas side.

## Outbound event types

The durable outbox currently emits these logical events:

- `participant.upsert`
- `obligation.upsert`
- `obligation.cancel`
- `obligation.close`
- `clearing.discover`
- `clearing.approve`
- `clearing.reject`

The backend configuration maps those event types to endpoint templates.

### participant.upsert payload

```json
{
  "source": "odoo",
  "source_instance_id": "...",
  "company": {
    "source_id": 1,
    "name": "Example GmbH",
    "vat": "DE...",
    "company_registry": "...",
    "country_code": "DE",
    "email": "..."
  }
}
```

A successful response may return either `participant_id` or `id`; the connector stores it as the company's Orbitas Participant Passport id.

### obligation.upsert payload

The payload is a normalized snapshot, not an Odoo record serialization.

Important fields include:

```json
{
  "source": {
    "system": "odoo",
    "instance_id": "...",
    "company_id": 1,
    "model": "account.move",
    "record_id": 42,
    "revision": "2026-09-18T..."
  },
  "obligation": {
    "kind": "invoice",
    "document_number": "INV/2026/0001",
    "currency": "EUR",
    "original_amount": "1000.00",
    "outstanding_amount": "750.00",
    "invoice_date": "2026-09-01",
    "due_date": "2026-10-01"
  },
  "debtor": {"...": "..."},
  "creditor": {"...": "..."}
}
```

For a customer invoice, the partner is debtor and the Odoo company is creditor. For a vendor bill, the Odoo company is debtor and the partner is creditor.

A successful response may return either `obligation_id` or `id`.

`obligation.cancel` is used when the source Odoo document itself is cancelled. `obligation.close` is used when the accounting obligation has been fully discharged in Odoo. These are deliberately different states.

## Inbound webhook

The generated route is:

```text
/orbitas/webhook/<backend_uuid>
```

Required headers:

```http
X-Orbitas-Event-Id: unique-event-id
X-Orbitas-Timestamp: unix-seconds
X-Orbitas-Signature: hex(hmac_sha256(secret, timestamp + "." + raw_body))
```

The connector rejects stale timestamps and duplicate event ids.

Accepted logical events:

### `clearing.proposal.upsert`

```json
{
  "type": "clearing.proposal.upsert",
  "data": {
    "id": "proposal-123",
    "source_obligation_id": "obl-123",
    "state": "candidate",
    "amount": "250.00",
    "currency": "EUR",
    "debtor_participant_id": "...",
    "intermediary_participant_id": "...",
    "creditor_participant_id": "...",
    "expires_at": "2026-09-20T12:00:00Z"
  }
}
```

### `settlement.instruction.upsert`

```json
{
  "type": "settlement.instruction.upsert",
  "data": {
    "id": "settlement-123",
    "proposal_id": "proposal-123",
    "state": "pending",
    "amount": "250.00",
    "currency": "EUR",
    "payer_participant_id": "...",
    "receiver_participant_id": "...",
    "payment_reference": "...",
    "evidence_reference": null
  }
}
```

## Explicit non-goals

The connector does not:

- compute the global clearing graph in Odoo;
- execute blockchain settlement itself;
- treat a proposal as consent;
- treat a settlement instruction as proof an invoice is paid;
- directly mutate derived Odoo accounting fields.
