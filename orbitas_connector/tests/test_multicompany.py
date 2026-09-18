from odoo.tests.common import TransactionCase, new_test_user


class TestOrbitasMultiCompany(TransactionCase):
    def test_backend_record_rule_is_company_scoped(self):
        company_a = self.env.company
        company_b = self.env["res.company"].create({"name": "Orbitas Other Company"})
        user = new_test_user(
            self.env,
            login="orbitas-company-a",
            groups="base.group_user,orbitas_connector.group_orbitas_user",
            company_id=company_a.id,
            company_ids=[(6, 0, [company_a.id])],
        )
        backend_b = self.env["orbitas.backend"].sudo().create(
            {
                "name": "Other Company Orbitas",
                "company_id": company_b.id,
                "base_url": "https://orbitas.invalid",
            }
        )
        visible = self.env["orbitas.backend"].with_user(user).search(
            [("id", "=", backend_b.id)]
        )
        self.assertFalse(visible)
