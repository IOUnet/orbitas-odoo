import json
import logging
from datetime import datetime, timezone

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class OrbitasInboundEvent(models.Model):
    _name = "orbitas.inbound.event"
    _description = "Orbitas Inbound Event"
    _order = "create_date desc"
    _check_company_auto = True

    backend_id = fields.Many2one(
        "orbitas.backend", required=True, ondelete="cascade", check_company=True, index=True
    )
    company_id = fields.Many2one(
        related="backend_id.company_id", store=True, readonly=True, index=True
    )
    remote_event_id = fields.Char(required=True, index=True, copy=False)
    event_type = fields.Char(required=True, index=True)
    payload_json = fields.Text(required=True)
    state = fields.Selection(
        [("received", "Received"), ("processed", "Processed"), ("error", "Error")],
        default="received",
        required=True,
        index=True,
    )
    processed_at = fields.Datetime(readonly=True)
    last_error = fields.Text(readonly=True)

    _sql_constraints = [
        (
            "orbitas_inbound_event_uniq",
            "unique(backend_id, remote_event_id)",
            "This Orbitas webhook event has already been received.",
        )
    ]

    @api.model
    def _parse_datetime(self, value):
        if not value:
            return False
        if isinstance(value, datetime):
            dt = value
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt

    @api.model
    def _currency_from_code(self, code):
        currency = self.env["res.currency"].search([("name", "=", code)], limit=1)
        if not currency:
            raise UserError(_("Unknown currency from Orbitas webhook: %s") % code)
        return currency

    def _upsert_proposal(self, data):
        self.ensure_one()
        remote_id = data.get("id")
        if not remote_id:
            raise UserError(_("Clearing proposal webhook is missing id."))
        Proposal = self.env["orbitas.clearing.proposal"]
        proposal = Proposal.search(
            [("backend_id", "=", self.backend_id.id), ("remote_proposal_id", "=", remote_id)],
            limit=1,
        )
        binding = False
        source_remote = data.get("source_obligation_id")
        if source_remote:
            binding = self.env["orbitas.obligation.binding"].search(
                [
                    ("backend_id", "=", self.backend_id.id),
                    ("remote_obligation_id", "=", source_remote),
                ],
                limit=1,
            )
        vals = {
            "backend_id": self.backend_id.id,
            "remote_proposal_id": remote_id,
            "source_binding_id": binding.id if binding else False,
            "state": data.get("state") if data.get("state") in dict(Proposal._fields["state"].selection) else "candidate",
            "amount": data.get("amount") or 0,
            "currency_id": self._currency_from_code(data.get("currency")).id,
            "debtor_participant_id": data.get("debtor_participant_id"),
            "intermediary_participant_id": data.get("intermediary_participant_id"),
            "creditor_participant_id": data.get("creditor_participant_id"),
            "expires_at": self._parse_datetime(data.get("expires_at")),
            "raw_payload_json": json.dumps(data, sort_keys=True, default=str),
        }
        if proposal:
            proposal.write(vals)
        else:
            proposal = Proposal.create(vals)
        return proposal

    def _upsert_settlement(self, data):
        self.ensure_one()
        remote_id = data.get("id")
        if not remote_id:
            raise UserError(_("Settlement instruction webhook is missing id."))
        Settlement = self.env["orbitas.settlement.instruction"]
        settlement = Settlement.search(
            [
                ("backend_id", "=", self.backend_id.id),
                ("remote_instruction_id", "=", remote_id),
            ],
            limit=1,
        )
        proposal = False
        if data.get("proposal_id"):
            proposal = self.env["orbitas.clearing.proposal"].search(
                [
                    ("backend_id", "=", self.backend_id.id),
                    ("remote_proposal_id", "=", data["proposal_id"]),
                ],
                limit=1,
            )
        state = data.get("state") or "pending"
        allowed_states = dict(Settlement._fields["state"].selection)
        vals = {
            "backend_id": self.backend_id.id,
            "proposal_id": proposal.id if proposal else False,
            "remote_instruction_id": remote_id,
            "state": state if state in allowed_states else "pending",
            "amount": data.get("amount") or 0,
            "currency_id": self._currency_from_code(data.get("currency")).id,
            "payer_participant_id": data.get("payer_participant_id"),
            "receiver_participant_id": data.get("receiver_participant_id"),
            "payment_reference": data.get("payment_reference"),
            "evidence_reference": data.get("evidence_reference"),
            "raw_payload_json": json.dumps(data, sort_keys=True, default=str),
        }
        if settlement:
            settlement.write(vals)
        else:
            settlement = Settlement.create(vals)
        if proposal and settlement.state == "settled":
            proposal.state = "settled"
        return settlement

    def _process(self):
        for event in self:
            if event.state == "processed":
                continue
            try:
                payload = json.loads(event.payload_json)
                data = payload.get("data") or {}
                if event.event_type == "clearing.proposal.upsert":
                    event._upsert_proposal(data)
                elif event.event_type == "settlement.instruction.upsert":
                    event._upsert_settlement(data)
                else:
                    raise UserError(_("Unsupported Orbitas webhook event type: %s") % event.event_type)
                event.write(
                    {
                        "state": "processed",
                        "processed_at": fields.Datetime.now(),
                        "last_error": False,
                    }
                )
            except Exception as exc:
                _logger.warning("Orbitas inbound event processing failed event=%s", event.id, exc_info=True)
                event.write({"state": "error", "last_error": str(exc)[:4000]})
                raise
        return True
