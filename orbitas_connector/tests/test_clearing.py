from odoo.tests.common import TransactionCase


class TestOrbitasClearing(TransactionCase):
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

    def test_approve_only_queues_consent(self):
        proposal = self.env["orbitas.clearing.proposal"].create(
            {
                "backend_id": self.backend.id,
                "remote_proposal_id": "proposal-1",
                "state": "candidate",
                "amount": 100,
                "currency_id": self.env.company.currency_id.id,
            }
        )
        proposal.action_approve()
        self.assertEqual(proposal.state, "approving")
        event = self.env["orbitas.outbox"].search([("proposal_id", "=", proposal.id)])
        self.assertEqual(len(event), 1)
        self.assertEqual(event.event_type, "clearing.approve")
