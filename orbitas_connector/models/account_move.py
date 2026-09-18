from decimal import Decimal

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    orbitas_binding_count = fields.Integer(
        compute="_compute_orbitas_binding_info",
        groups="orbitas_connector.group_orbitas_user",
    )
    orbitas_sync_state = fields.Char(
        compute="_compute_orbitas_binding_info",
        groups="orbitas_connector.group_orbitas_user",
    )
    orbitas_remote_obligation_id = fields.Char(
        compute="_compute_orbitas_binding_info",
        groups="orbitas_connector.group_orbitas_user",
    )

    def _compute_orbitas_binding_info(self):
        by_move = {}
        if self.ids:
            bindings = self.env["orbitas.obligation.binding"].sudo().search(
                [
                    ("source_model", "=", "account.move"),
                    ("source_record_id", "in", self.ids),
                    ("company_id", "in", self.company_id.ids),
                ]
            )
            for binding in bindings:
                by_move.setdefault(binding.source_record_id, []).append(binding)
        for move in self:
            rows = by_move.get(move.id, [])
            move.orbitas_binding_count = len(rows)
            first = rows[0] if rows else False
            move.orbitas_sync_state = first.sync_state if first else False
            move.orbitas_remote_obligation_id = first.remote_obligation_id if first else False

    def _orbitas_is_eligible(self):
        self.ensure_one()
        return (
            self.state == "posted"
            and self.move_type in ("out_invoice", "in_invoice")
            and self.amount_residual > 0
        )

    def _orbitas_party_payload(self, partner, *, role, backend, is_company=False):
        self.ensure_one()
        if is_company:
            company = self.company_id
            return {
                "role": role,
                "participant_id": backend.participant_passport_id or None,
                "source": {
                    "system": "odoo",
                    "kind": "company",
                    "id": company.id,
                    "name": company.name,
                    "vat": company.vat or None,
                    "company_registry": company.company_registry or None,
                    "country_code": company.country_id.code or None,
                },
            }
        commercial = partner.commercial_partner_id
        return {
            "role": role,
            "participant_id": None,
            "source": {
                "system": "odoo",
                "kind": "partner",
                "id": commercial.id,
                "name": commercial.name,
                "vat": commercial.vat or None,
                "company_registry": getattr(commercial, "company_registry", False) or None,
                "country_code": commercial.country_id.code or None,
                "email": commercial.email or None,
            },
        }

    def _orbitas_prepare_obligation_payload(self, backend):
        self.ensure_one()
        if self.move_type not in ("out_invoice", "in_invoice"):
            raise UserError(_("Orbitas MVP exports customer invoices and vendor bills only."))

        company_party = self._orbitas_party_payload(
            self.company_id.partner_id, role="creditor", backend=backend, is_company=True
        )
        partner_party = self._orbitas_party_payload(
            self.partner_id, role="debtor", backend=backend, is_company=False
        )
        if self.move_type == "in_invoice":
            company_party["role"] = "debtor"
            partner_party["role"] = "creditor"

        debtor = company_party if company_party["role"] == "debtor" else partner_party
        creditor = company_party if company_party["role"] == "creditor" else partner_party
        currency = self.currency_id
        original = Decimal(str(abs(self.amount_total)))
        outstanding = Decimal(str(abs(self.amount_residual)))

        return {
            "source": {
                "system": "odoo",
                "instance_id": backend.source_instance_id,
                "company_id": self.company_id.id,
                "model": self._name,
                "record_id": self.id,
                "revision": self.write_date and fields.Datetime.to_string(self.write_date),
            },
            "obligation": {
                "kind": "invoice",
                "document_type": self.move_type,
                "document_number": self.name or None,
                "source_reference": self.ref or None,
                "currency": currency.name,
                "original_amount": format(original, "f"),
                "outstanding_amount": format(outstanding, "f"),
                "invoice_date": fields.Date.to_string(self.invoice_date) if self.invoice_date else None,
                "due_date": fields.Date.to_string(self.invoice_date_due) if self.invoice_date_due else None,
                "accounting_state": self.state,
                "payment_state": self.payment_state or None,
            },
            "debtor": debtor,
            "creditor": creditor,
        }

    def _orbitas_get_or_create_binding(self, backend):
        self.ensure_one()
        Binding = self.env["orbitas.obligation.binding"].sudo()
        binding = Binding.search(
            [
                ("backend_id", "=", backend.id),
                ("source_model", "=", self._name),
                ("source_record_id", "=", self.id),
            ],
            limit=1,
        )
        if not binding:
            binding = Binding.create(
                {
                    "backend_id": backend.id,
                    "source_model": self._name,
                    "source_record_id": self.id,
                    "source_display_name": self.display_name,
                }
            )
        return binding

    def action_orbitas_export(self):
        if not self.env.user.has_group("orbitas_connector.group_orbitas_user"):
            raise UserError(_("You do not have permission to synchronize invoices with Orbitas."))
        for move in self:
            if not move._orbitas_is_eligible():
                raise UserError(
                    _("Only posted customer invoices and vendor bills with an outstanding balance can be exported to Orbitas.")
                )
            backend = self.env["orbitas.backend"]._get_for_company(move.company_id)
            if not backend.participant_passport_id:
                raise UserError(
                    _("The company must be linked to an Orbitas Participant Passport before exporting obligations.")
                )
            binding = move._orbitas_get_or_create_binding(backend)
            binding._enqueue_current_state(force=True)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Orbitas"),
                "message": _("Orbitas obligation synchronization queued."),
                "type": "success",
            },
        }

    def action_open_orbitas_binding(self):
        self.ensure_one()
        if not self.env.user.has_group("orbitas_connector.group_orbitas_user"):
            raise UserError(_("You do not have permission to view Orbitas bindings."))
        bindings = self.env["orbitas.obligation.binding"].search(
            [("source_model", "=", self._name), ("source_record_id", "=", self.id)]
        )
        action = self.env.ref("orbitas_connector.action_orbitas_bindings").read()[0]
        action["domain"] = [("id", "in", bindings.ids)]
        if len(bindings) == 1:
            action.update({"view_mode": "form", "res_id": bindings.id, "views": [(False, "form")]})
        return action

    def action_orbitas_find_clearing(self):
        self.ensure_one()
        if not self.env.user.has_group("orbitas_connector.group_orbitas_user"):
            raise UserError(_("You do not have permission to request Orbitas clearing proposals."))
        bindings = self.env["orbitas.obligation.binding"].search(
            [("source_model", "=", self._name), ("source_record_id", "=", self.id)],
            limit=2,
        )
        if len(bindings) != 1 or not bindings.remote_obligation_id:
            raise UserError(_("Synchronize this invoice/bill with Orbitas before searching for clearing opportunities."))
        now_key = fields.Datetime.to_string(fields.Datetime.now())[:16]
        payload = {
            "participant_id": bindings.backend_id.participant_passport_id,
            "source_obligation_id": bindings.remote_obligation_id,
        }
        self.env["orbitas.outbox"].sudo()._enqueue(
            bindings.backend_id,
            "clearing.discover",
            payload,
            idempotency_key=f"clearing-discover:{bindings.id}:{now_key}",
            binding=bindings.sudo(),
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Orbitas"),
                "message": _("Clearing search queued. Candidate proposals will appear in Orbitas → Clearing → Proposals."),
                "type": "success",
            },
        }

    def action_post(self):
        result = super().action_post()
        for move in self.filtered(lambda m: m.move_type in ("out_invoice", "in_invoice")):
            backends = self.env["orbitas.backend"].sudo().search(
                [
                    ("company_id", "=", move.company_id.id),
                    ("active", "=", True),
                    ("auto_export_posted", "=", True),
                ],
                limit=2,
            )
            if len(backends) == 1 and backends.participant_passport_id and move.amount_residual > 0:
                move._orbitas_get_or_create_binding(backends)._enqueue_current_state(force=True)
        return result
