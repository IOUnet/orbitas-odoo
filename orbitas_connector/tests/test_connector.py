from odoo.tests.common import TransactionCase


class TestOrbitasConnector(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.backend = cls.env["orbitas.backend"].create(
            {
                "name": "Test Orbitas",
                "company_id": cls.env.company.id,
                "base_url": "https://orbitas.invalid",
                "participant_passport_id": "participant-company",
            }
        )
        cls.partner = cls.env["res.partner"].create({"name": "Counterparty"})

    def test_customer_invoice_direction(self):
        move = self.env["account.move"].create(
            {"move_type": "out_invoice", "partner_id": self.partner.id}
        )
        payload = move._orbitas_prepare_obligation_payload(self.backend)
        self.assertEqual(payload["debtor"]["source"]["id"], self.partner.id)
        self.assertEqual(payload["creditor"]["participant_id"], "participant-company")

    def test_vendor_bill_direction(self):
        move = self.env["account.move"].create(
            {"move_type": "in_invoice", "partner_id": self.partner.id}
        )
        payload = move._orbitas_prepare_obligation_payload(self.backend)
        self.assertEqual(payload["creditor"]["source"]["id"], self.partner.id)
        self.assertEqual(payload["debtor"]["participant_id"], "participant-company")

    def test_credit_note_is_not_mvp_eligible(self):
        move = self.env["account.move"].create(
            {"move_type": "out_refund", "partner_id": self.partner.id}
        )
        self.assertFalse(move._orbitas_is_eligible())
