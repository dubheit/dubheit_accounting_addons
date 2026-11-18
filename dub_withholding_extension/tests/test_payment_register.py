# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date

from odoo import Command
from odoo.tests import new_test_user
from odoo.tools.safe_eval import safe_eval

from .common import WithholdingCommon


class TestPaymentRegister(WithholdingCommon):
    def test_partial_payments_split_by_year(self):
        bill = self._wt_invoice(
            "in_invoice", 1000.0, self.vat_purchase + self.wt_purchase, "2025-12-01"
        )
        total = bill.amount_total  # 1000 + 220 - 200 = 1020
        self._wt_pay(bill, total / 2, "2025-12-20")
        self._wt_pay(bill, total / 2, "2026-01-10")
        rows = self._register_rows(bill)
        self.assertRecordValues(
            rows,
            [
                {
                    "source": "core",
                    "wt_kind": "operated",
                    "payment_date": date(2025, 12, 20),
                    "amount": 100.0,
                    "gross_amount": 500.0,
                    "taxable_amount": 500.0,
                    "paid_f24": False,
                    "amount_paid_f24": 0.0,
                },
                {
                    "source": "core",
                    "wt_kind": "operated",
                    "payment_date": date(2026, 1, 10),
                    "amount": 100.0,
                    "gross_amount": 500.0,
                    "taxable_amount": 500.0,
                    "paid_f24": False,
                    "amount_paid_f24": 0.0,
                },
            ],
        )
        self.assertEqual(rows.mapped("id"), [r.move_line_id.id * 2 for r in rows])

    def test_23_base50_taxable(self):
        bill = self._wt_invoice(
            "in_invoice", 1000.0, self.vat_purchase + self.wt_23_purchase, "2025-12-01"
        )
        self._wt_pay(bill, bill.amount_total, "2025-12-20")
        self.assertRecordValues(
            self._register_rows(bill),
            [
                {
                    "amount": 115.0,
                    "gross_amount": 1000.0,
                    "taxable_amount": 500.0,
                    "reason": "ZO",
                }
            ],
        )

    def test_unreconciled_payment_disappears(self):
        bill = self._wt_invoice(
            "in_invoice", 1000.0, self.vat_purchase + self.wt_purchase, "2025-12-01"
        )
        payment = self._wt_pay(bill, bill.amount_total, "2025-12-20")
        self.assertTrue(self._register_rows(bill))
        payment.action_draft()
        self.assertFalse(self._register_rows(bill))

    def test_payment_date_is_the_payment(self):
        # bill registered after the payment
        bill = self._wt_invoice(
            "in_invoice", 1000.0, self.vat_purchase + self.wt_purchase, "2026-01-20"
        )
        self._wt_pay(bill, bill.amount_total, "2025-12-28")
        self.assertEqual(self._register_rows(bill).payment_date, date(2025, 12, 28))

    def test_payment_date_before_lock_date(self):
        # payment matched after its period was locked: the cash basis entry
        # moves after the lock date, the register keeps the payment date
        bill = self._wt_invoice(
            "in_invoice", 1000.0, self.vat_purchase + self.wt_purchase, "2026-01-20"
        )
        self._wt_pay_after_lock(bill, "2025-12-28", "2025-12-31")
        row = self._register_rows(bill)
        self.assertGreater(row.move_line_id.move_id.date, date(2025, 12, 31))
        self.assertEqual(row.payment_date, date(2025, 12, 28))

    def test_start_date_on_payment_date(self):
        bill = self._wt_invoice(
            "in_invoice", 1000.0, self.vat_purchase + self.wt_purchase, "2026-01-20"
        )
        self._wt_pay_after_lock(bill, "2025-12-28", "2025-12-31")
        self.company.l10n_it_wt_start_date = "2026-01-01"
        self.assertFalse(self._register_rows(bill))

    def test_cu_only_irpef(self):
        enasarco = (
            self.env["account.chart.template"]
            .with_company(self.company)
            .ref("enasarcoa")
        )
        bill = self._wt_invoice(
            "in_invoice",
            1000.0,
            self.vat_purchase + self.wt_23_purchase + enasarco,
            "2025-12-01",
        )
        self._wt_pay(bill, bill.amount_total, "2025-12-20")
        rows = self._register_rows(bill)
        self.assertEqual(rows.tax_id, self.wt_23_purchase | enasarco)
        self.assertEqual(rows.filtered("irpef").tax_id, self.wt_23_purchase)
        action = self.env.ref("dub_withholding_extension.action_withholding_cu_summary")
        cu_rows = self.env["l10n_it.withholding.tax.report"].search(
            safe_eval(action.domain) + [("invoice_id", "=", bill.id)]
        )
        self.assertEqual(cu_rows.tax_id, self.wt_23_purchase)

    def test_sale_withholding_is_suffered(self):
        inv = self._wt_invoice(
            "out_invoice", 1000.0, self.vat_sale + self.wt_sale, "2025-12-01"
        )
        self._wt_pay(inv, inv.amount_total, "2025-12-20")
        self.assertRecordValues(
            self._register_rows(inv), [{"wt_kind": "suffered", "amount": 200.0}]
        )

    def test_refund_is_negative(self):
        refund = self._wt_invoice(
            "in_refund", 1000.0, self.vat_purchase + self.wt_purchase, "2025-12-01"
        )
        self._wt_pay(refund, refund.amount_total, "2025-12-20")
        self.assertRecordValues(
            self._register_rows(refund),
            [{"amount": -200.0, "gross_amount": -1000.0}],
        )

    def test_start_date_excludes_earlier_rows(self):
        bill = self._wt_invoice(
            "in_invoice", 1000.0, self.vat_purchase + self.wt_purchase, "2025-12-01"
        )
        self._wt_pay(bill, bill.amount_total, "2025-12-20")
        self.company.l10n_it_wt_start_date = "2025-12-21"
        self.assertFalse(self._register_rows(bill))

    def test_history_rows(self):
        bill = self._wt_invoice("in_invoice", 400.0, self.vat_purchase, "2022-03-01")
        st = self.env["withholding.history.statement"].create(
            {
                "company_id": self.company.id,
                "partner_id": self.partner_a.id,
                "invoice_id": bill.id,
                "date": "2022-03-01",
                "wt_kind": "operated",
                "withholding_code": "RitPF23",
                "reason": "T",
                "gross_amount": 400.0,
                "taxable_amount": 200.0,
                "amount": 46.0,
                "move_ids": [
                    Command.create(
                        {
                            "partner_id": self.partner_a.id,
                            "date": "2022-04-01",
                            "amount": 23.0,
                            "state": "paid",
                        }
                    )
                ],
            }
        )
        self.assertRecordValues(
            self._register_rows(bill),
            [
                {
                    "id": st.move_ids.id * 2 + 1,
                    "source": "oca",
                    "amount": 23.0,
                    "gross_amount": 200.0,
                    "taxable_amount": 100.0,
                    "paid_f24": True,
                    "amount_paid_f24": 23.0,
                    "reason": "T",
                    "payment_date": date(2022, 4, 1),
                }
            ],
        )

    def test_other_company_rows_hidden(self):
        bill = self._wt_invoice(
            "in_invoice", 1000.0, self.vat_purchase + self.wt_purchase, "2025-12-01"
        )
        self._wt_pay(bill, bill.amount_total, "2025-12-20")
        other = self.setup_other_company(name="Other WT")["company"]
        user = new_test_user(
            self.env,
            "wt_other",
            groups="account.group_account_user",
            company_id=other.id,
            company_ids=[Command.set(other.ids)],
        )
        self.env.flush_all()
        self.assertFalse(
            self.env["l10n_it.withholding.tax.report"]
            .with_user(user)
            .search([("invoice_id", "=", bill.id)])
        )
