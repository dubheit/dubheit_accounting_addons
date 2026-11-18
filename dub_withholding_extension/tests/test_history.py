# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from psycopg2 import IntegrityError

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged
from odoo.tools import mute_logger

from .common import WithholdingCommon


@tagged("post_install", "-at_install")
class TestHistory(WithholdingCommon):
    def _statement(self, **vals):
        return self.env["withholding.history.statement"].create(
            {
                "company_id": self.company.id,
                "partner_id": self.partner_a.id,
                "date": "2024-03-01",
                "wt_kind": "operated",
                "withholding_code": "1040",
                "reason": "A",
                "gross_amount": 1000.0,
                "taxable_amount": 1000.0,
                "amount": 200.0,
                **vals,
            }
        )

    def test_amount_paid(self):
        st = self._statement(
            move_ids=[
                Command.create(
                    {
                        "partner_id": self.partner_a.id,
                        "date": "2024-04-01",
                        "amount": 120.0,
                    }
                ),
                Command.create(
                    {
                        "partner_id": self.partner_a.id,
                        "date": "2024-05-01",
                        "amount": 80.0,
                        "state": "paid",
                    }
                ),
            ]
        )
        self.assertEqual(st.amount_paid, 200.0)

    def test_user_cannot_edit_manager_can(self):
        st = self._statement()
        user = new_test_user(
            self.env,
            "wt_user",
            groups="account.group_account_user",
            company_id=self.company.id,
        )
        manager = new_test_user(
            self.env,
            "wt_manager",
            groups="account.group_account_manager",
            company_id=self.company.id,
        )
        user.company_ids |= self.company
        manager.company_ids |= self.company
        with self.assertRaises(AccessError):
            st.with_user(user).write({"amount": 1.0})
        st.with_user(manager).write({"amount": 190.0})
        self.assertEqual(st.amount, 190.0)

    def test_amount_paid_refreshes(self):
        st = self._statement(
            move_ids=[
                Command.create(
                    {
                        "partner_id": self.partner_a.id,
                        "date": "2024-04-01",
                        "amount": 100.0,
                    }
                ),
            ]
        )
        self.assertEqual(st.amount_paid, 100.0)
        st.move_ids[0].amount = 150.0
        self.assertEqual(st.amount_paid, 150.0)
        st.write(
            {
                "move_ids": [
                    Command.create(
                        {
                            "partner_id": self.partner_a.id,
                            "date": "2024-05-01",
                            "amount": 25.0,
                        }
                    )
                ]
            }
        )
        self.assertEqual(st.amount_paid, 175.0)

    def test_manual_rows_without_oca_id(self):
        st1 = self._statement(oca_id=0)
        st2 = self._statement(oca_id=0)
        self.assertTrue(st1 and st2)

    def test_oca_id_unique_when_positive(self):
        self._statement(oca_id=7)
        with self.assertRaises(IntegrityError), mute_logger(
            "odoo.sql_db"
        ), self.env.cr.savepoint():
            self._statement(oca_id=7)
