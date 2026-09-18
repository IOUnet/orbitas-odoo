import hashlib
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
import uuid

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)


class OrbitasBackend(models.Model):
    _name = "orbitas.backend"
    _description = "Orbitas Backend"
    _order = "company_id, id"
    _check_company_auto = True

    name = fields.Char(required=True, default="Orbitas")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        ondelete="cascade",
    )
    source_instance_id = fields.Char(
        required=True,
        default=lambda self: str(uuid.uuid4()),
        help="Stable identifier of this Odoo installation/connector instance.",
    )
    participant_passport_id = fields.Char(
        string="Participant Passport ID",
        copy=False,
        help="Orbitas participant identifier for this Odoo company.",
    )
    base_url = fields.Char(required=True, default="https://api.orbitas.example")
    api_token = fields.Char(groups="orbitas_connector.group_orbitas_manager", copy=False)
    request_timeout_seconds = fields.Integer(default=15)
    auto_export_posted = fields.Boolean(
        string="Automatically export posted invoices/bills",
        default=False,
    )

    participant_upsert_path = fields.Char(default="/api/v1/participants")
    obligation_upsert_path = fields.Char(default="/api/v1/obligations")
    obligation_cancel_path = fields.Char(default="/api/v1/obligations/{remote_id}/cancel")
    obligation_close_path = fields.Char(default="/api/v1/obligations/{remote_id}/close")
    clearing_discover_path = fields.Char(default="/api/v1/clearing/discover")
    proposal_action_path = fields.Char(
        default="/api/v1/clearing/proposals/{proposal_id}/{action}"
    )
    health_path = fields.Char(default="/health")

    webhook_uuid = fields.Char(required=True, default=lambda self: str(uuid.uuid4()), copy=False)
    webhook_secret = fields.Char(
        required=True,
        default=lambda self: uuid.uuid4().hex + uuid.uuid4().hex,
        copy=False,
        groups="orbitas_connector.group_orbitas_manager",
    )
    webhook_tolerance_seconds = fields.Integer(default=300)

    last_success_at = fields.Datetime(readonly=True, copy=False)
    last_error_at = fields.Datetime(readonly=True, copy=False)
    last_error_category = fields.Char(readonly=True, copy=False)
    pending_outbox_count = fields.Integer(compute="_compute_outbox_health")
    retry_outbox_count = fields.Integer(compute="_compute_outbox_health")
    oldest_pending_at = fields.Datetime(compute="_compute_outbox_health")

    _sql_constraints = [
        (
            "orbitas_backend_source_instance_company_uniq",
            "unique(company_id, source_instance_id)",
            "The Orbitas source instance id must be unique per company.",
        ),
        (
            "orbitas_backend_webhook_uuid_uniq",
            "unique(webhook_uuid)",
            "The Orbitas webhook UUID must be unique.",
        ),
    ]

    @api.constrains("base_url")
    def _check_base_url(self):
        for backend in self:
            parsed = urllib.parse.urlparse(backend.base_url or "")
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValidationError(_("Orbitas Base URL must be an absolute HTTP(S) URL."))

    def _compute_outbox_health(self):
        Outbox = self.env["orbitas.outbox"].sudo()
        for backend in self:
            rows = Outbox.search(
                [
                    ("backend_id", "=", backend.id),
                    ("state", "in", ("pending", "retry")),
                ],
                order="create_date asc",
            )
            backend.pending_outbox_count = len(rows.filtered(lambda r: r.state == "pending"))
            backend.retry_outbox_count = len(rows.filtered(lambda r: r.state == "retry"))
            backend.oldest_pending_at = rows[:1].create_date if rows else False

    @api.model
    def _get_for_company(self, company):
        backends = self.search(
            [("company_id", "=", company.id), ("active", "=", True)], limit=2
        )
        if not backends:
            raise UserError(_("No active Orbitas backend is configured for %s.") % company.display_name)
        if len(backends) > 1:
            raise UserError(
                _("More than one active Orbitas backend is configured for %s.")
                % company.display_name
            )
        return backends

    def _join_url(self, path):
        self.ensure_one()
        return urllib.parse.urljoin(self.base_url.rstrip("/") + "/", (path or "").lstrip("/"))

    def _headers(self, *, idempotency_key=None):
        self.ensure_one()
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def _http_json(self, method, path, *, payload=None, idempotency_key=None):
        self.ensure_one()
        body = None
        if payload is not None:
            body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        http_request = urllib.request.Request(
            self._join_url(path),
            data=body,
            headers=self._headers(idempotency_key=idempotency_key),
            method=method,
        )
        try:
            with urllib.request.urlopen(
                http_request, timeout=max(1, self.request_timeout_seconds or 15)
            ) as response:
                raw = response.read() or b"{}"
                data = json.loads(raw.decode("utf-8")) if raw else {}
                return response.status, data
        except urllib.error.HTTPError as exc:
            raw = exc.read() or b"{}"
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                data = {"error": "remote_http_error"}
            return exc.code, data

    def _event_request(self, event_type, payload):
        self.ensure_one()
        if event_type == "participant.upsert":
            return "POST", self.participant_upsert_path
        if event_type == "obligation.upsert":
            return "POST", self.obligation_upsert_path
        if event_type == "obligation.cancel":
            remote_id = payload.get("remote_id")
            if not remote_id:
                raise UserError(_("Cannot cancel an Orbitas obligation without a remote id."))
            return "POST", self.obligation_cancel_path.format(remote_id=remote_id)
        if event_type == "obligation.close":
            remote_id = payload.get("remote_id")
            if not remote_id:
                raise UserError(_("Cannot close an Orbitas obligation without a remote id."))
            return "POST", self.obligation_close_path.format(remote_id=remote_id)
        if event_type == "clearing.discover":
            return "POST", self.clearing_discover_path
        if event_type in ("clearing.approve", "clearing.reject"):
            action = "approve" if event_type.endswith("approve") else "reject"
            proposal_id = payload.get("proposal_id")
            if not proposal_id:
                raise UserError(_("Clearing action is missing proposal_id."))
            return "POST", self.proposal_action_path.format(
                proposal_id=proposal_id, action=action
            )
        raise UserError(_("Unsupported Orbitas outbox event type: %s") % event_type)

    def _send_outbox_event(self, event):
        self.ensure_one()
        payload = json.loads(event.payload_json)
        method, path = self._event_request(event.event_type, payload)
        return self._http_json(
            method,
            path,
            payload=payload,
            idempotency_key=event.idempotency_key,
        )

    def _company_participant_payload(self):
        self.ensure_one()
        company = self.company_id
        return {
            "source": "odoo",
            "source_instance_id": self.source_instance_id,
            "company": {
                "source_id": company.id,
                "name": company.name,
                "vat": company.vat or None,
                "company_registry": company.company_registry or None,
                "country_code": company.country_id.code or None,
                "email": company.email or None,
            },
        }

    def _ensure_manager(self):
        if not self.env.user.has_group("orbitas_connector.group_orbitas_manager"):
            raise AccessError(_("Only Orbitas Managers can configure or operate the backend."))

    def action_register_participant(self):
        self.ensure_one()
        self._ensure_manager()
        payload = self._company_participant_payload()
        fingerprint = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        self.env["orbitas.outbox"]._enqueue(
            self,
            "participant.upsert",
            payload,
            idempotency_key=f"participant:{self.id}:{fingerprint}",
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Orbitas"),
                "message": _("Participant Passport synchronization queued."),
                "type": "success",
            },
        }

    def action_test_connection(self):
        self.ensure_one()
        self._ensure_manager()
        status, _payload = self._http_json("GET", self.health_path)
        if not 200 <= status < 300:
            raise UserError(_("Orbitas health check returned HTTP %s.") % status)
        self.last_success_at = fields.Datetime.now()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Orbitas"),
                "message": _("Connection succeeded."),
                "type": "success",
            },
        }

    def action_process_outbox(self):
        self.ensure_one()
        self._ensure_manager()
        self.env["orbitas.outbox"]._process_batch(backend=self, limit=100)
        return True

    def action_open_outbox(self):
        self.ensure_one()
        action = self.env.ref("orbitas_connector.action_orbitas_outbox").read()[0]
        action["domain"] = [("backend_id", "=", self.id)]
        return action

    def _record_transport_error(self, category):
        self.ensure_one()
        self.write(
            {
                "last_error_at": fields.Datetime.now(),
                "last_error_category": category,
            }
        )

    def _record_transport_success(self):
        self.ensure_one()
        self.write(
            {
                "last_success_at": fields.Datetime.now(),
                "last_error_category": False,
            }
        )
