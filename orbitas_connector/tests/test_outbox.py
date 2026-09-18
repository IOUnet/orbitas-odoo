from odoo.tests.common import TransactionCase


class TestOrbitasOutbox(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.backend = cls.env["orbitas.backend"].create(
            {
                "name": "Test Orbitas",
                "company_id": cls.env.company.id,
                "base_url": "https://orbitas.invalid",
            }
        )

    def test_enqueue_is_idempotent(self):
        Outbox = self.env["orbitas.outbox"]
        payload = {"hello": "world"}
        first = Outbox._enqueue(
            self.backend,
            "participant.upsert",
            payload,
            idempotency_key="same-operation",
        )
        second = Outbox._enqueue(
            self.backend,
            "participant.upsert",
            payload,
            idempotency_key="same-operation",
        )
        self.assertEqual(first, second)
        self.assertEqual(
            Outbox.search_count(
                [("backend_id", "=", self.backend.id), ("idempotency_key", "=", "same-operation")]
            ),
            1,
        )
