import hashlib

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


class OrbitasClearingProposal(models.Model):
    _name = "orbitas.clearing.proposal"
    _description = "Orbitas Clearing Proposal"
    _order = "create_date desc"
    _check_company_auto = True

    backend_id = fields.Many2one(
        "orbitas.backend", required=True, ondelete="cascade", check_company=True, index=True
    )
    company_id = fields.Many2one(
        related="backend_id.company_id", store=True, readonly=True, index=True
    )
    remote_proposal_id = fields.Char(required=True, index=True, copy=False)
    source_binding_id = fields.Many2one(
        "orbitas.obligation.binding", ondelete="set null", check_company=True
    )
    source_move_id = fields.Many2one(
        "account.move",
        compute="_compute_source_move_id",
        string="Source Invoice/Bill",
    )
    state = fields.Selection(
        [
            ("candidate", "Candidate"),
            ("approving", "Approval queued"),
            ("approved", "Approved"),
            ("rejecting", "Rejection queued"),
            ("rejected", "Rejected"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
            ("settled", "Settled"),
        ],
        default="candidate",
        required=True,
        index=True,
    )
    amount = fields.Monetary(required=True, currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", required=True)
    debtor_participant_id = fields.Char()
    intermediary_participant_id = fields.Char()
    creditor_participant_id = fields.Char()
    expires_at = fields.Datetime()
    raw_payload_json = fields.Text(readonly=True)
    settlement_instruction_ids = fields.One2many(
        "orbitas.settlement.instruction", "proposal_id"
    )

    _sql_constraints = [
        (
            "orbitas_proposal_remote_uniq",
            "unique(backend_id, remote_proposal_id)",
            "This Orbitas clearing proposal already exists.",
        )
    ]

    def _compute_source_move_id(self):
        for proposal in self:
            binding = proposal.source_binding_id
            proposal.source_move_id = (
                self.env["account.move"].browse(binding.source_record_id)
                if binding and binding.source_model == "account.move"
                else False
            )

    def _check_actionable(self):
        self.ensure_one()
        if self.state != "candidate":
            raise UserError(_("Only candidate proposals can be approved or rejected."))
        if self.expires_at and self.expires_at < fields.Datetime.now():
            self.sudo().state = "expired"
            raise UserError(_("This clearing proposal has expired."))

    def _enqueue_action(self, action):
        self.ensure_one()
        if not self.env.user.has_group("orbitas_connector.group_orbitas_user"):
            raise AccessError(_("You do not have permission to decide Orbitas clearing proposals."))
        self._check_actionable()
        payload = {
            "proposal_id": self.remote_proposal_id,
            "participant_id": self.backend_id.participant_passport_id,
            "decision": action,
        }
        digest = hashlib.sha256(
            f"{self.remote_proposal_id}:{action}".encode("utf-8")
        ).hexdigest()
        event_type = f"clearing.{action}"
        self.env["orbitas.outbox"].sudo()._enqueue(
            self.backend_id,
            event_type,
            payload,
            idempotency_key=f"proposal:{self.id}:{digest}",
            proposal=self.sudo(),
        )
        self.sudo().state = "approving" if action == "approve" else "rejecting"

    def action_approve(self):
        for proposal in self:
            proposal._enqueue_action("approve")
        return True

    def action_reject(self):
        for proposal in self:
            proposal._enqueue_action("reject")
        return True

    def action_open_source_move(self):
        self.ensure_one()
        if not self.source_move_id:
            raise UserError(_("No Odoo invoice/bill is linked to this proposal."))
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.source_move_id.id,
        }


class OrbitasSettlementInstruction(models.Model):
    _name = "orbitas.settlement.instruction"
    _description = "Orbitas Settlement Instruction"
    _order = "create_date desc"
    _check_company_auto = True

    backend_id = fields.Many2one(
        "orbitas.backend", required=True, ondelete="cascade", check_company=True, index=True
    )
    company_id = fields.Many2one(
        related="backend_id.company_id", store=True, readonly=True, index=True
    )
    proposal_id = fields.Many2one(
        "orbitas.clearing.proposal", ondelete="set null", check_company=True, index=True
    )
    remote_instruction_id = fields.Char(required=True, index=True, copy=False)
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("locked", "Locked"),
            ("settled", "Settled"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    amount = fields.Monetary(required=True, currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", required=True)
    payer_participant_id = fields.Char()
    receiver_participant_id = fields.Char()
    payment_reference = fields.Char()
    evidence_reference = fields.Char()
    accounting_reconciled = fields.Boolean(
        default=False,
        help="Informational flag only. It must be set by an explicit accounting workflow after reconciliation.",
    )
    raw_payload_json = fields.Text(readonly=True)

    _sql_constraints = [
        (
            "orbitas_settlement_remote_uniq",
            "unique(backend_id, remote_instruction_id)",
            "This Orbitas settlement instruction already exists.",
        )
    ]

    def action_open_source_move(self):
        self.ensure_one()
        if not self.proposal_id.source_move_id:
            raise UserError(_("No Odoo invoice/bill is linked to this settlement instruction."))
        return self.proposal_id.action_open_source_move()

    def action_confirm_accounting_reconciled(self):
        if not self.env.user.has_group("orbitas_connector.group_orbitas_manager"):
            raise AccessError(_("Only Orbitas Managers can confirm accounting reconciliation."))
        for instruction in self:
            move = instruction.proposal_id.source_move_id
            if not move:
                raise UserError(_("No Odoo invoice/bill is linked to this settlement instruction."))
            if not move.currency_id.is_zero(move.amount_residual):
                raise UserError(
                    _("The linked invoice/bill still has an outstanding accounting balance. Reconcile it through Odoo Accounting first.")
                )
            instruction.sudo().accounting_reconciled = True
        return True
