import hashlib
import json
import logging
from datetime import timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class OrbitasOutbox(models.Model):
    _name = "orbitas.outbox"
    _description = "Orbitas Durable Outbox"
    _order = "create_date asc, id asc"
    _check_company_auto = True

    backend_id = fields.Many2one(
        "orbitas.backend", required=True, ondelete="cascade", check_company=True, index=True
    )
    company_id = fields.Many2one(
        related="backend_id.company_id", store=True, readonly=True, index=True
    )
    binding_id = fields.Many2one(
        "orbitas.obligation.binding", ondelete="set null", check_company=True, index=True
    )
    proposal_id = fields.Many2one(
        "orbitas.clearing.proposal", ondelete="set null", check_company=True, index=True
    )
    event_type = fields.Selection(
        [
            ("participant.upsert", "Participant upsert"),
            ("obligation.upsert", "Obligation upsert"),
            ("obligation.cancel", "Obligation cancel"),
            ("obligation.close", "Obligation close"),
            ("clearing.discover", "Clearing discovery"),
            ("clearing.approve", "Clearing approve"),
            ("clearing.reject", "Clearing reject"),
        ],
        required=True,
        index=True,
    )
    idempotency_key = fields.Char(required=True, index=True, copy=False)
    payload_json = fields.Text(required=True)
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("done", "Done"),
            ("retry", "Retry"),
            ("dead", "Dead letter"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    attempt_count = fields.Integer(default=0, readonly=True)
    max_attempts = fields.Integer(default=8)
    next_attempt_at = fields.Datetime(index=True)
    last_attempt_at = fields.Datetime(readonly=True)
    completed_at = fields.Datetime(readonly=True)
    response_hash = fields.Char(readonly=True, copy=False)
    remote_reference = fields.Char(readonly=True, copy=False)
    last_error_category = fields.Char(readonly=True, copy=False)
    last_error = fields.Text(readonly=True, copy=False)

    _sql_constraints = [
        (
            "orbitas_outbox_idempotency_uniq",
            "unique(backend_id, idempotency_key)",
            "This Orbitas operation has already been queued.",
        )
    ]

    @api.model
    def _enqueue(
        self,
        backend,
        event_type,
        payload,
        *,
        idempotency_key,
        binding=None,
        proposal=None,
    ):
        existing = self.search(
            [("backend_id", "=", backend.id), ("idempotency_key", "=", idempotency_key)],
            limit=1,
        )
        if existing:
            return existing
        return self.create(
            {
                "backend_id": backend.id,
                "binding_id": binding.id if binding else False,
                "proposal_id": proposal.id if proposal else False,
                "event_type": event_type,
                "idempotency_key": idempotency_key,
                "payload_json": json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str),
                "state": "pending",
            }
        )

    def _retry_delay(self):
        self.ensure_one()
        seconds = min(3600, 30 * (2 ** max(0, self.attempt_count - 1)))
        return timedelta(seconds=seconds)

    def _remote_reference_from_response(self, response):
        self.ensure_one()
        if not isinstance(response, dict):
            return False
        if self.event_type == "participant.upsert":
            return response.get("participant_id") or response.get("id")
        if self.event_type.startswith("obligation."):
            return response.get("obligation_id") or response.get("id")
        if self.event_type.startswith("clearing."):
            return response.get("proposal_id") or response.get("id")
        return response.get("id")

    def _apply_success(self, response):
        self.ensure_one()
        remote_ref = self._remote_reference_from_response(response)
        vals = {
            "state": "done",
            "completed_at": fields.Datetime.now(),
            "remote_reference": remote_ref or self.remote_reference,
            "last_error": False,
            "last_error_category": False,
            "response_hash": hashlib.sha256(
                json.dumps(response or {}, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
            ).hexdigest(),
        }
        self.write(vals)
        if self.event_type == "participant.upsert" and remote_ref:
            self.backend_id.participant_passport_id = remote_ref
        elif self.binding_id:
            binding_vals = {"last_sync_at": fields.Datetime.now(), "last_error": False}
            if self.event_type == "obligation.upsert":
                binding_vals.update({"sync_state": "synced"})
                if remote_ref:
                    binding_vals["remote_obligation_id"] = remote_ref
            elif self.event_type == "obligation.cancel":
                binding_vals["sync_state"] = "cancelled"
            elif self.event_type == "obligation.close":
                binding_vals["sync_state"] = "closed"
            self.binding_id.write(binding_vals)
        if self.proposal_id:
            if self.event_type == "clearing.approve":
                self.proposal_id.state = "approved"
            elif self.event_type == "clearing.reject":
                self.proposal_id.state = "rejected"
        self.backend_id._record_transport_success()

    def _apply_failure(self, *, category, message, retryable):
        self.ensure_one()
        now = fields.Datetime.now()
        attempts = self.attempt_count
        should_retry = retryable and attempts < self.max_attempts
        vals = {
            "state": "retry" if should_retry else "dead",
            "last_error_category": category,
            "last_error": (message or category)[:4000],
            "next_attempt_at": now + self._retry_delay() if should_retry else False,
        }
        self.write(vals)
        if self.binding_id:
            self.binding_id.write({"sync_state": "error", "last_error": vals["last_error"]})
        self.backend_id._record_transport_error(category)

    def _process_one(self):
        self.ensure_one()
        if self.state not in ("pending", "retry", "processing"):
            return
        self.write(
            {
                "state": "processing",
                "attempt_count": self.attempt_count + 1,
                "last_attempt_at": fields.Datetime.now(),
            }
        )
        try:
            status, response = self.backend_id._send_outbox_event(self)
        except Exception as exc:
            _logger.warning(
                "Orbitas outbox transport exception backend=%s outbox=%s category=transport",
                self.backend_id.id,
                self.id,
                exc_info=True,
            )
            self._apply_failure(category="transport", message=str(exc), retryable=True)
            return

        if 200 <= status < 300:
            self._apply_success(response)
            return
        if status == 429 or status >= 500:
            self._apply_failure(
                category=f"http_{status}",
                message=(response or {}).get("error") if isinstance(response, dict) else str(response),
                retryable=True,
            )
            return
        self._apply_failure(
            category=f"http_{status}",
            message=(response or {}).get("error") if isinstance(response, dict) else str(response),
            retryable=False,
        )

    @api.model
    def _process_batch(self, *, backend=None, limit=100):
        domain = [
            ("state", "in", ("pending", "retry")),
            "|",
            ("next_attempt_at", "=", False),
            ("next_attempt_at", "<=", fields.Datetime.now()),
        ]
        if backend:
            domain.append(("backend_id", "=", backend.id))
        events = self.search(domain, order="create_date asc, id asc", limit=limit)
        for event in events:
            event._process_one()
        return len(events)

    @api.model
    def _cron_process_outbox(self):
        return self._process_batch(limit=100)
