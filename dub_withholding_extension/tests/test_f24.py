# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import importlib.util
from datetime import date

from odoo import Command
from odoo.exceptions import UserError
from odoo.tools.misc import file_path
from odoo.tools.safe_eval import safe_eval

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
        cls.wt_pg = (
            cls.env["account.chart.template"].with_company(cls.company).ref("20awc")
        )

    def _f24(self, payment_type=None, **vals):
        payment_type = payment_type or self.f24_type
        return self.env["withholding.payment"].create(
            {"type_id": payment_type.id, "date": "2026-01-16", **vals}
        )

    def _type_pg(self):
        """Second type on the same core account (20awc, legal persons)."""
        return self.f24_type.copy(
            {"name": "1040 PG", "tax_ids": [Command.set(self.wt_pg.ids)]}
        )

    def _paid_bill(self, taxes):
        bill = self._wt_invoice(
            "in_invoice", 1000.0, self.vat_purchase + taxes, "2025-12-01"
        )
        self._wt_pay(bill, bill.amount_total, "2025-12-20")
        return bill

    def _manual_wt_line(self, amount, entry_date):
        """Untaxed line on the core payable account (e.g. a manual closing)."""
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "date": entry_date,
                "line_ids": [
                    Command.create(
                        {"account_id": self.wt_payable.id, "credit": amount}
                    ),
                    Command.create(
                        {
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "debit": amount,
                        }
                    ),
                ],
            }
        )
        move.action_post()
        return move.line_ids.filtered(
            lambda line: line.account_id == self.wt_payable
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
                    "amount_paid_f24": 200.0,
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

    def test_types_sharing_account_load_own_lines(self):
        type_pg = self._type_pg()
        self.assertEqual(type_pg.account_ids, self.f24_type.account_ids)
        bill_pf = self._paid_bill(self.wt_purchase)
        bill_pg = self._paid_bill(self.wt_pg)
        line_pf = self._register_rows(bill_pf).move_line_id
        line_pg = self._register_rows(bill_pg).move_line_id
        self.assertEqual(line_pf.account_id, line_pg.account_id)
        f24_pf = self._f24()
        f24_pf.action_load_lines()
        self.assertEqual(f24_pf.move_line_ids, line_pf)
        f24_pg = self._f24(type_pg)
        f24_pg.action_load_lines()
        self.assertEqual(f24_pg.move_line_ids, line_pg)
        f24_pf.action_confirm()
        f24_pg.action_load_lines()
        self.assertEqual(f24_pg.move_line_ids, line_pg)
        self.assertEqual(f24_pg.amount, 200.0)
        f24_pf_again = self._f24()
        f24_pf_again.action_load_lines()
        self.assertFalse(f24_pf_again.move_line_ids)

    def test_untaxed_line_only_on_unshared_account(self):
        manual = self._manual_wt_line(50.0, "2025-12-22")
        f24 = self._f24()
        f24.action_load_lines()
        self.assertEqual(f24.move_line_ids, manual)
        self._type_pg()
        f24.action_load_lines()
        self.assertFalse(f24.move_line_ids)

    def test_confirm_rejects_other_tax(self):
        bill_pg = self._paid_bill(self.wt_pg)
        f24 = self._f24(
            move_line_ids=[
                Command.set(self._register_rows(bill_pg).move_line_id.ids)
            ]
        )
        with self.assertRaises(UserError):
            f24.action_confirm()

    def test_period_on_payment_date(self):
        # the cash basis entry goes after the lock date, the payment is in
        # December: the F24 of December pays it
        bill = self._wt_invoice(
            "in_invoice", 1000.0, self.vat_purchase + self.wt_purchase, "2026-01-20"
        )
        self._wt_pay_after_lock(bill, "2025-12-28", "2025-12-31")
        line = self._register_rows(bill).move_line_id
        self.assertGreater(line.date, date(2025, 12, 31))
        december = self._f24(date_start="2025-12-01", date_stop="2025-12-31")
        december.action_load_lines()
        self.assertEqual(december.move_line_ids, line)
        january = self._f24(date_start="2026-01-01", date_stop="2026-01-31")
        january.action_load_lines()
        self.assertFalse(january.move_line_ids)

    def _break_type_accounts(self):
        """Payment type as left by 18.0.2.0.0: no accounts, 2602 not
        reconcilable."""
        cr = self.env.cr
        cr.execute(
            "DELETE FROM wt_payment_type_account_rel WHERE type_id = %s",
            [self.f24_type.id],
        )
        cr.execute(
            "UPDATE account_account SET reconcile = FALSE WHERE id = %s",
            [self.wt_payable.id],
        )
        self.env.invalidate_all()
        self.assertFalse(self.f24_type.account_ids)
        self.assertFalse(self.wt_payable.reconcile)

    def test_refresh_accounts(self):
        self._break_type_accounts()
        self.f24_type._l10n_it_wt_refresh_accounts()
        self.assertEqual(self.f24_type.account_ids, self.wt_payable)
        self.assertTrue(self.wt_payable.reconcile)

    def test_migration_script(self):
        self._break_type_accounts()
        self.f24_type.active = False
        report_filter = self.env["ir.filters"].create(
            {
                "name": "Old register filter",
                "model_id": "l10n_it.withholding.tax.report",
                "active": False,
            }
        )
        path = file_path(
            "dub_withholding_extension/migrations/18.0.3.0.0/post-migrate.py"
        )
        spec = importlib.util.spec_from_file_location("wt_post_migrate", path)
        script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(script)
        script.migrate(self.env.cr, "18.0.2.0.0")
        self.env.invalidate_all()
        self.assertEqual(self.f24_type.account_ids, self.wt_payable)
        self.assertTrue(self.wt_payable.reconcile)
        self.assertFalse(report_filter.exists())

    def test_reconciled_elsewhere_not_to_pay(self):
        bill = self._paid_bill(self.wt_purchase)
        line = self._register_rows(bill).move_line_id
        closing = self.env["account.move"].create(
            {
                "move_type": "entry",
                "date": "2026-01-16",
                "line_ids": [
                    Command.create(
                        {"account_id": self.wt_payable.id, "debit": 200.0}
                    ),
                    Command.create(
                        {
                            "account_id": self.f24_type.counterpart_account_id.id,
                            "credit": 200.0,
                        }
                    ),
                ],
            }
        )
        closing.action_post()
        (
            line
            | closing.line_ids.filtered(
                lambda aml: aml.account_id == self.wt_payable
            )
        ).reconcile()
        self.assertRecordValues(
            self._register_rows(bill),
            [{"reconciled": True, "paid_f24": False, "amount_paid_f24": 0.0}],
        )
        action = self.env.ref("dub_withholding_extension.action_withholding_due_lines")
        self.assertFalse(
            self.env["l10n_it.withholding.tax.report"].search(
                safe_eval(action.domain) + [("invoice_id", "=", bill.id)]
            )
        )
