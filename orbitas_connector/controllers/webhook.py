import hashlib
import hmac
import json
import time

from odoo import http
from odoo.http import request


class OrbitasWebhookController(http.Controller):
    @http.route(
        "/orbitas/webhook/<string:backend_uuid>",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def orbitas_webhook(self, backend_uuid, **_kwargs):
        raw = request.httprequest.get_data(cache=False, as_text=False) or b""
        event_id = request.httprequest.headers.get("X-Orbitas-Event-Id")
        timestamp = request.httprequest.headers.get("X-Orbitas-Timestamp")
        signature = request.httprequest.headers.get("X-Orbitas-Signature")

        backend = request.env["orbitas.backend"].sudo().search(
            [("webhook_uuid", "=", backend_uuid), ("active", "=", True)], limit=1
        )
        if not backend or not event_id or not timestamp or not signature:
            return request.make_json_response({"error": "unauthorized"}, status=401)

        try:
            timestamp_int = int(timestamp)
        except ValueError:
            return request.make_json_response({"error": "invalid_timestamp"}, status=401)
        if abs(int(time.time()) - timestamp_int) > max(1, backend.webhook_tolerance_seconds):
            return request.make_json_response({"error": "stale_timestamp"}, status=401)

        signed = timestamp.encode("utf-8") + b"." + raw
        expected = hmac.new(
            backend.webhook_secret.encode("utf-8"), signed, hashlib.sha256
        ).hexdigest()
        normalized_signature = signature.removeprefix("sha256=")
        if not hmac.compare_digest(expected, normalized_signature):
            return request.make_json_response({"error": "invalid_signature"}, status=401)

        Event = request.env["orbitas.inbound.event"].sudo()
        existing = Event.search(
            [("backend_id", "=", backend.id), ("remote_event_id", "=", event_id)], limit=1
        )
        if existing:
            return request.make_json_response({"status": "duplicate"}, status=200)

        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return request.make_json_response({"error": "invalid_json"}, status=400)
        event_type = payload.get("type")
        if not event_type:
            return request.make_json_response({"error": "missing_type"}, status=400)

        event = Event.create(
            {
                "backend_id": backend.id,
                "remote_event_id": event_id,
                "event_type": event_type,
                "payload_json": json.dumps(payload, sort_keys=True, default=str),
            }
        )
        try:
            event._process()
        except Exception:
            return request.make_json_response({"error": "processing_failed"}, status=422)
        return request.make_json_response({"status": "accepted"}, status=202)
