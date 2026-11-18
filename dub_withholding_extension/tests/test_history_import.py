# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.addons.dub_withholding_extension.models.withholding_history import (
    oca_gross_taxable,
)

from .common import WithholdingCommon

OCA_DDL = """
CREATE TABLE payment_reason (id int PRIMARY KEY, code varchar);
CREATE TABLE withholding_tax (id int PRIMARY KEY, code varchar, name varchar, payment_reason_id int, company_id int);
CREATE TABLE withholding_tax_rate (id serial PRIMARY KEY, withholding_tax_id int, date_start date, date_stop date, tax float8, base float8);
CREATE TABLE withholding_tax_statement (id int PRIMARY KEY, move_id int, partner_id int, date date, base float8, tax float8, withholding_tax_id int, wt_type varchar);
CREATE TABLE withholding_tax_move (id int PRIMARY KEY, statement_id int, partner_id int, date date, amount float8, state varchar);
"""


class TestHistoryImport(WithholdingCommon):
    def test_gross_taxable_rules(self):
        self.assertEqual(oca_gross_taxable(1000.0, 200.0, 20.0, 1.0), (1000.0, 1000.0))
        self.assertEqual(oca_gross_taxable(400.0, 46.0, 23.0, 0.5), (400.0, 200.0))  # base = gross
        self.assertEqual(oca_gross_taxable(184.43, 42.42, 23.0, 0.5), (368.86, 184.43))  # base = taxable
        self.assertEqual(oca_gross_taxable(-3087.58, -617.52, 20.0, 1.0), (-3087.58, -3087.58))
        self.assertEqual(oca_gross_taxable(100.0, 30.0, 20.0, 1.0), (150.0, 150.0))  # inconsistent: from withholding
        self.assertEqual(oca_gross_taxable(0.0, 0.0, 4.0, 1.0), (0.0, 0.0))
        self.assertEqual(oca_gross_taxable(500.0, 0.0, 0.0, 1.0), (500.0, 500.0))  # rate 0

    def _load_oca(self, bill):
        cr = self.env.cr
        cr.execute(OCA_DDL)
        cr.execute(
            """
            INSERT INTO payment_reason VALUES (1, 'A'), (2, 'T');
            INSERT INTO withholding_tax VALUES (1, '1040', 'Ritenuta 1040', 1, %(c)s), (2, 'RitPF23', 'Ritenuta 23%%', 2, %(c)s);
            INSERT INTO withholding_tax_rate (withholding_tax_id, tax, base) VALUES (1, 20, 1), (2, 23, 0.5);
            INSERT INTO withholding_tax_statement VALUES
                (10, %(m)s, %(p)s, '2024-03-01', 1000, 200, 1, 'in'),
                (11, %(m)s, %(p)s, '2022-05-01', 400, 46, 2, 'in'),
                (12, 999999999, %(p)s, '2021-01-01', 100, 20, 1, 'out');
            INSERT INTO withholding_tax_move VALUES
                (20, 10, %(p)s, '2024-04-01', 100, 'paid'), (21, 10, %(p)s, '2024-05-01', 100, 'due');
            """,
            {"c": self.company.id, "m": bill.id, "p": self.partner_a.id},
        )

    def test_import_and_idempotency(self):
        bill = self._wt_invoice("in_invoice", 1000.0, self.vat_purchase, "2024-03-01")
        self._load_oca(bill)
        Statement = self.env["withholding.history.statement"]
        self.assertEqual(Statement._import_from_oca(), {"statements": 3, "moves": 2})
        self.assertEqual(Statement._import_from_oca(), {"statements": 0, "moves": 0})
        st10 = Statement.search([("oca_id", "=", 10)])
        self.assertRecordValues(
            st10,
            [
                {
                    "invoice_id": bill.id,
                    "wt_kind": "operated",
                    "reason": "A",
                    "withholding_code": "1040",
                    "gross_amount": 1000.0,
                    "taxable_amount": 1000.0,
                    "amount": 200.0,
                    "amount_paid": 200.0,
                }
            ],
        )
        self.assertEqual(st10.move_ids.sorted("date").mapped("state"), ["paid", "due"])
        self.assertRecordValues(
            Statement.search([("oca_id", "=", 11)]),
            [{"gross_amount": 400.0, "taxable_amount": 200.0, "reason": "T"}],
        )

    def test_import_statement_with_missing_move(self):
        bill = self._wt_invoice("in_invoice", 1000.0, self.vat_purchase, "2024-03-01")
        self._load_oca(bill)
        self.env["withholding.history.statement"]._import_from_oca()
        st12 = self.env["withholding.history.statement"].search([("oca_id", "=", 12)])
        self.assertRecordValues(
            st12,
            [{"invoice_id": False, "wt_kind": "suffered", "company_id": self.company.id}],
        )

    def test_no_oca_tables(self):
        self.assertEqual(
            self.env["withholding.history.statement"]._import_from_oca(),
            {"statements": 0, "moves": 0},
        )
