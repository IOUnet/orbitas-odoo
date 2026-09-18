import hashlib
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class OrbitasObligationBinding(models.Model):
    _name = "orbitas.obligation.binding"
    _description = "Orbitas Obligation Binding"
    _order = "id desc"
    _check_company_auto = True

    backend_id = fields.Many2one(
        "orbitas.backend", required=True, ondelete="cascade", check_company=True, index=True
    )
    company_id = fields.Many2one(
        related="backend_id.company_id", store=True, readonly=True, index=True
    )
    source_model = fields.Char(required=True, default="account.move", index=True)
    source_record_id = fields.Integer(required=True, index=True)
    source_display_name = fields.Char(readonly=True)
    remote_obligation_id = fields.Char(index=True, copy=False)
    sync_state = fields.Selection(
        [
            ("new", "New"),
            ("queued", "Queued"),
            ("synced", "Synced"),
            ("cancel_queued", "Cancellation queued"),
            ("cancelled", "Cancelled"),
            ("close_queued", "Close queued"),
            ("closed", "Closed"),
            ("error", "Error"),
        ],
        default="new",
        required=True,
        index=True,
    )
    last_payload_hash = fields.Char(copy=False, index=True)
    last_source_revision = fields.Char(copy=False)
    last_sync_at = fields.Datetime(copy=False)
    last_error = fields.Text(copy=False)
    outbox_ids = fields.One2many("orbitas.outbox", "binding_id")

    _sql_constraints = [
        (
            "orbitas_binding_source_uniq",
            "unique(backend_id, source_model, source_record_id)",
            "This Odoo source record is already bound to Orbitas for this backend.",
        ),
        (
            "orbitas_binding_remote_uniq",
            "unique(backend_id, remote_obligation_id)",
            "This Orbitas obligation is already bound to another source record.",
        ),
    ]

    def _source_record(self):
        self.ensure_one()
        try:
            model = self.env[self.source_model]
        except KeyError as exc:
            raise UserError(_("Unknown source model %s") % self.source_model) from exc
        record = model.browse(self.source_record_id).exists()
        if not record:
            raise UserError(_("The source Odoo record no longer exists."))
        return record

    @api.model
    def _payload_hash(self, payload):
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _enqueue_current_state(self, *, force=False):
        for binding in self:
            source = binding._source_record()
            if binding.source_model != "account.move":
                raise UserError(_("Only account.move bindings are currently supported."))

            if source.state == "cancel" or source.amount_residual <= 0:
                if not binding.remote_obligation_id:
                    continue
                is_cancel = source.state == "cancel"
                event_type = "obligation.cancel" if is_cancel else "obligation.close"
                target_state = "cancel_queued" if is_cancel else "close_queued"
                final_state = "cancelled" if is_cancel else "closed"
                payload = {
                    "remote_id": binding.remote_obligation_id,
                    "source": {
                        "system": "odoo",
                        "instance_id": binding.backend_id.source_instance_id,
                        "company_id": source.company_id.id,
                        "model": source._name,
                        "record_id": source.id,
                    },
                    "reason": "cancelled" if is_cancel else "fully_discharged",
                }
                digest = binding._payload_hash(payload)
                if not force and binding.last_payload_hash == digest and binding.sync_state == final_state:
                    continue
                self.env["orbitas.outbox"]._enqueue(
                    binding.backend_id,
                    event_type,
                    payload,
                    idempotency_key=f"{event_type}:{binding.id}:{digest}",
                    binding=binding,
                )
                binding.write(
                    {
                        "sync_state": target_state,
                        "last_payload_hash": digest,
                        "last_source_revision": source.write_date and fields.Datetime.to_string(source.write_date),
                    }
                )
                continue

            if not source._orbitas_is_eligible():
                continue
            payload = source._orbitas_prepare_obligation_payload(binding.backend_id)
            digest = binding._payload_hash(payload)
            if not force and binding.last_payload_hash == digest and binding.sync_state == "synced":
                continue
            self.env["orbitas.outbox"]._enqueue(
                binding.backend_id,
                "obligation.upsert",
                payload,
                idempotency_key=f"obligation-upsert:{binding.id}:{digest}",
                binding=binding,
            )
            binding.write(
                {
                    "sync_state": "queued",
                    "source_display_name": source.display_name,
                    "last_payload_hash": digest,
                    "last_source_revision": source.write_date and fields.Datetime.to_string(source.write_date),
                    "last_error": False,
                }
            )
        return True

    @api.model
    def _cron_refresh_bound_moves(self):
        bindings = self.search(
            [("source_model", "=", "account.move"), ("backend_id.active", "=", True)],
            limit=500,
            order="id asc",
        )
        bindings._enqueue_current_state(force=False)
