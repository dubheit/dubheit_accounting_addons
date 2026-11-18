# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command

from .common import WithholdingCommon


class TestInvoiceRegister(WithholdingCommon):
    def _rows(self, invoice):
        self.env.flush_all()
        return self.env["l10n_it.withholding.invoice.report"].search(
            [("invoice_id", "=", invoice.id)]
        )

    def test_partially_paid(self):
        bill = self._wt_invoice(
            "in_invoice", 1000.0, self.vat_purchase + self.wt_purchase, "2025-12-01"
        )
        self._wt_pay(bill, bill.amount_total / 2, "2025-12-20")
        self.assertRecordValues(
            self._rows(bill),
            [
                {
                    "source": "core",
                    "gross_amount": 1000.0,
                    "taxable_amount": 1000.0,
                    "amount": 200.0,
                    "amount_paid": 100.0,
                    "amount_residual": 100.0,
                }
            ],
        )

    def test_draft_invoice_excluded(self):
        bill = self._wt_invoice(
            "in_invoice",
            1000.0,
            self.vat_purchase + self.wt_purchase,
            "2025-12-01",
            post=False,
        )
        self.assertFalse(self._rows(bill))

    def test_refund_negative(self):
        refund = self._wt_invoice(
            "in_refund", 1000.0, self.vat_purchase + self.wt_purchase, "2025-12-01"
        )
        self.assertRecordValues(
            self._rows(refund),
            [{"gross_amount": -1000.0, "amount": -200.0, "amount_residual": -200.0}],
        )

    def test_history_paid_and_residual(self):
        bill = self._wt_invoice("in_invoice", 1000.0, self.vat_purchase, "2023-02-01")
        self.env["withholding.history.statement"].create(
            {
                "company_id": self.company.id,
                "partner_id": self.partner_a.id,
                "invoice_id": bill.id,
                "date": "2023-02-01",
                "wt_kind": "operated",
                "gross_amount": 1000.0,
                "taxable_amount": 1000.0,
                "amount": 200.0,
                "move_ids": [
                    Command.create(
                        {
                            "partner_id": self.partner_a.id,
                            "date": "2023-03-01",
                            "amount": 120.0,
                        }
                    )
                ],
            }
        )
        self.assertRecordValues(
            self._rows(bill),
            [{"source": "oca", "amount_paid": 120.0, "amount_residual": 80.0}],
        )
