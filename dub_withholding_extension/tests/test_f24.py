# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date

from odoo import Command

from .common import WithholdingCommon


class TestF24(WithholdingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.f24_type = cls.env["withholding.payment.type"].create(
            {
                "name": "1040",
                "codice_tributo": "1040",
                "tax_ids": [Command.set(cls.wt_purchase.ids)],
                "journal_id": cls.company_data["default_journal_misc"].id,
                "counterpart_account_id": cls.company_data[
                    "default_journal_bank"
                ].default_account_id.id,
            }
        )

    def test_type_makes_core_account_reconcilable(self):
        self.assertIn(self.wt_payable, self.f24_type.account_ids)
        self.assertTrue(self.wt_payable.reconcile)
        self.assertIn("2602", " ".join(self.f24_type.message_ids.mapped("body")))

    def test_f24_marks_rows_paid(self):
        bill = self._wt_invoice(
            "in_invoice", 1000.0, self.vat_purchase + self.wt_purchase, "2025-12-01"
        )
        self._wt_pay(bill, bill.amount_total, "2025-12-20")
        f24 = self.env["withholding.payment"].create(
            {"type_id": self.f24_type.id, "date": "2026-01-16"}
        )
        f24.action_load_lines()
        self.assertEqual(f24.amount, 200.0)
        f24.action_confirm()
        self.assertRecordValues(
            self._register_rows(bill),
            [
                {
                    "paid_f24": True,
                    "withholding_payment_id": f24.id,
                    "f24_date": date(2026, 1, 16),
                }
            ],
        )

    def test_load_lines_respects_start_date(self):
        bill = self._wt_invoice(
            "in_invoice", 1000.0, self.vat_purchase + self.wt_purchase, "2025-12-01"
        )
        self._wt_pay(bill, bill.amount_total, "2025-12-20")
        self.company.l10n_it_wt_start_date = "2025-12-21"
        f24 = self.env["withholding.payment"].create(
            {"type_id": self.f24_type.id, "date": "2026-01-16"}
        )
        f24.action_load_lines()
        self.assertFalse(f24.move_line_ids)

    def test_warning_on_invoice_tax(self):
        self.assertFalse(self.f24_type.l10n_it_wt_config_warning)
        on_invoice = self.wt_purchase.copy({"tax_exigibility": "on_invoice"})
        self.f24_type.tax_ids = [Command.link(on_invoice.id)]
        self.assertTrue(self.f24_type.l10n_it_wt_config_warning)

    def test_suffered_not_loaded(self):
        inv = self._wt_invoice(
            "out_invoice", 1000.0, self.vat_sale + self.wt_sale, "2025-12-01"
        )
        self._wt_pay(inv, inv.amount_total, "2025-12-20")
        f24 = self.env["withholding.payment"].create(
            {"type_id": self.f24_type.id, "date": "2026-01-16"}
        )
        f24.action_load_lines()
        self.assertFalse(f24.move_line_ids)

    def test_wizard_takes_only_core_operated_rows(self):
        bill = self._wt_invoice(
            "in_invoice", 1000.0, self.vat_purchase + self.wt_purchase, "2025-12-01"
        )
        self._wt_pay(bill, bill.amount_total, "2025-12-20")
        inv = self._wt_invoice(
            "out_invoice", 1000.0, self.vat_sale + self.wt_sale, "2025-12-01"
        )
        self._wt_pay(inv, inv.amount_total, "2025-12-20")
        hist_bill = self._wt_invoice(
            "in_invoice", 400.0, self.vat_purchase, "2022-03-01"
        )
        self.env["withholding.history.statement"].create(
            {
                "company_id": self.company.id,
                "partner_id": self.partner_a.id,
                "invoice_id": hist_bill.id,
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
        operated = self._register_rows(bill)
        suffered = self._register_rows(inv)
        history = self._register_rows(hist_bill)
        self.assertEqual(
            (operated.source, operated.wt_kind), ("core", "operated")
        )
        self.assertEqual(suffered.wt_kind, "suffered")
        self.assertTrue(history)
        rows = operated | suffered | history
        wizard = (
            self.env["withholding.payment.create"]
            .with_context(
                active_model="l10n_it.withholding.tax.report", active_ids=rows.ids
            )
            .create({"type_id": self.f24_type.id})
        )
        self.assertEqual(wizard.line_ids, operated.move_line_id)
