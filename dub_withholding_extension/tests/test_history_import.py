# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tools.sql import table_exists

from odoo.addons.dub_withholding_extension.models.withholding_history import (
    oca_gross_taxable,
)

from .common import WithholdingCommon

OCA_DDL = """
CREATE TABLE payment_reason (id int PRIMARY KEY, code varchar);
CREATE TABLE withholding_tax (
    id int PRIMARY KEY, code varchar, name varchar, payment_reason_id int,
    company_id int);
CREATE TABLE withholding_tax_rate (
    id serial PRIMARY KEY, withholding_tax_id int, date_start date,
    date_stop date, tax float8, base float8);
CREATE TABLE withholding_tax_statement (
    id int PRIMARY KEY, move_id int, partner_id int, date date, base float8,
    tax float8, withholding_tax_id int, wt_type varchar);
CREATE TABLE withholding_tax_move (
    id int PRIMARY KEY, statement_id int, partner_id int, date date,
    amount float8, state varchar);
"""


class TestHistoryImport(WithholdingCommon):
    def test_gross_taxable_rules(self):
        cases = [
            ((1000.0, 200.0, 20.0, 1.0), (1000.0, 1000.0)),
            ((400.0, 46.0, 23.0, 0.5), (400.0, 200.0)),  # base = gross
            ((184.43, 42.42, 23.0, 0.5), (368.86, 184.43)),  # base = taxable
            ((-3087.58, -617.52, 20.0, 1.0), (-3087.58, -3087.58)),
            # inconsistent: from the withholding
            ((100.0, 30.0, 20.0, 1.0), (150.0, 150.0)),
            ((0.0, 0.0, 4.0, 1.0), (0.0, 0.0)),
            ((500.0, 0.0, 0.0, 1.0), (500.0, 500.0)),  # rate 0
            # half-cent taxes: OCA rounded base * (rate / 100)
            ((500.5, 115.12, 23.0, 0.5), (1001.0, 500.5)),
            ((450.5, 103.62, 23.0, 1.0), (450.5, 450.5)),
            ((1001.0, 115.12, 23.0, 0.5), (1001.0, 500.5)),
        ]
        for args, expected in cases:
            self.assertEqual(oca_gross_taxable(*args), expected, args)

    def _skip_if_oca_tables(self):
        if table_exists(self.env.cr, "withholding_tax_statement"):
            self.skipTest("OCA withholding tables already in this database")

    def _create_oca_tables(self, ddl=OCA_DDL):
        self._skip_if_oca_tables()
        self.env.cr.execute(ddl)

    def _bill(self):
        return self._wt_invoice(
            "in_invoice", 1000.0, self.vat_purchase, "2024-03-01"
        )

    def _load_oca(self, bill):
        self._create_oca_tables()
        self.env.cr.execute(
            """
            INSERT INTO payment_reason VALUES (1, 'A'), (2, 'T');
            INSERT INTO withholding_tax VALUES
                (1, '1040', 'Ritenuta 1040', 1, %(c)s),
                (2, 'RitPF23', 'Ritenuta 23%%', 2, %(c)s);
            INSERT INTO withholding_tax_rate (withholding_tax_id, tax, base)
            VALUES (1, 20, 1), (2, 23, 0.5);
            INSERT INTO withholding_tax_statement VALUES
                (10, %(m)s, %(p)s, '2024-03-01', 1000, 200, 1, 'in'),
                (11, %(m)s, %(p)s, '2022-05-01', 400, 46, 2, 'in'),
                (12, 999999999, %(p)s, '2021-01-01', 100, 20, 1, 'out');
            INSERT INTO withholding_tax_move VALUES
                (20, 10, %(p)s, '2024-04-01', 100, 'paid'),
                (21, 10, %(p)s, '2024-05-01', 100, 'due');
            """,
            {"c": self.company.id, "m": bill.id, "p": self.partner_a.id},
        )

    def test_import_and_idempotency(self):
        bill = self._bill()
        self._load_oca(bill)
        Statement = self.env["withholding.history.statement"]
        self.assertEqual(Statement._import_from_oca(), {"statements": 3, "moves": 2})
        self.assertEqual(Statement._import_from_oca(), {"statements": 0, "moves": 0})
        st10 = Statement.search([("oca_id", "=", 10)])
        self.assertRecordValues(
            st10,
            [
                {
                    "oca_wt_types": False,
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
        self.assertEqual(
            st10.move_ids.sorted("date").mapped("state"), ["paid", "due"]
        )
        self.assertRecordValues(
            Statement.search([("oca_id", "=", 11)]),
            [{"gross_amount": 400.0, "taxable_amount": 200.0, "reason": "T"}],
        )

    def test_import_statement_with_missing_move(self):
        bill = self._bill()
        self._load_oca(bill)
        self.env["withholding.history.statement"]._import_from_oca()
        st12 = self.env["withholding.history.statement"].search([("oca_id", "=", 12)])
        self.assertRecordValues(
            st12,
            [
                {
                    "invoice_id": False,
                    "wt_kind": "suffered",
                    "company_id": self.company.id,
                }
            ],
        )

    def test_no_oca_tables(self):
        self._skip_if_oca_tables()
        self.assertEqual(
            self.env["withholding.history.statement"]._import_from_oca(),
            {"statements": 0, "moves": 0},
        )

    def test_reason_from_causale_pagamento(self):
        bill = self._bill()
        cr = self.env.cr
        ddl = OCA_DDL.replace("payment_reason_id", "causale_pagamento_id").replace(
            "payment_reason (id int PRIMARY KEY, code varchar)",
            "causale_pagamento (id int PRIMARY KEY, code varchar, name varchar)",
        )
        self._create_oca_tables(ddl)
        cr.execute(
            """
            INSERT INTO causale_pagamento VALUES (1, 'A', 'x');
            INSERT INTO withholding_tax VALUES
                (1, '1040', 'Ritenuta 1040', 1, %(c)s);
            INSERT INTO withholding_tax_rate (withholding_tax_id, tax, base)
            VALUES (1, 20, 1);
            INSERT INTO withholding_tax_statement VALUES
                (10, %(m)s, %(p)s, '2024-03-01', 1000, 200, 1, 'in');
            """,
            {"c": self.company.id, "m": bill.id, "p": self.partner_a.id},
        )
        Statement = self.env["withholding.history.statement"]
        self.assertEqual(Statement._import_from_oca(), {"statements": 1, "moves": 0})
        self.assertEqual(Statement.search([("oca_id", "=", 10)]).reason, "A")

    def test_no_reason_table(self):
        bill = self._bill()
        cr = self.env.cr
        ddl = OCA_DDL.replace(
            "CREATE TABLE payment_reason (id int PRIMARY KEY, code varchar);", ""
        )
        self._create_oca_tables(ddl)
        cr.execute(
            """
            INSERT INTO withholding_tax VALUES
                (1, '1040', 'Ritenuta 1040', 1, %(c)s);
            INSERT INTO withholding_tax_rate (withholding_tax_id, tax, base)
            VALUES (1, 20, 1);
            INSERT INTO withholding_tax_statement VALUES
                (10, %(m)s, %(p)s, '2024-03-01', 1000, 200, 1, 'in');
            """,
            {"c": self.company.id, "m": bill.id, "p": self.partner_a.id},
        )
        Statement = self.env["withholding.history.statement"]
        self.assertEqual(Statement._import_from_oca(), {"statements": 1, "moves": 0})
        self.assertFalse(Statement.search([("oca_id", "=", 10)]).reason)

    def test_rate_by_date_and_fallback(self):
        bill = self._bill()
        cr = self.env.cr
        self._create_oca_tables()
        cr.execute(
            """
            INSERT INTO withholding_tax VALUES (1, 'X', 'Rit X', NULL, %(c)s);
            INSERT INTO withholding_tax_rate
                   (withholding_tax_id, date_start, date_stop, tax, base)
            VALUES
                (1, '2020-01-01', '2021-12-31', 20, 1),
                (1, '2022-01-01', NULL, 23, 0.5);
            INSERT INTO withholding_tax_statement VALUES
                (10, %(m)s, %(p)s, '2021-06-01', 1000, 200, 1, 'in'),
                (11, %(m)s, %(p)s, '2023-06-01', 400, 46, 1, 'in'),
                (12, %(m)s, %(p)s, '2019-06-01', 400, 46, 1, 'in');
            """,
            {"c": self.company.id, "m": bill.id, "p": self.partner_a.id},
        )
        Statement = self.env["withholding.history.statement"]
        self.assertEqual(Statement._import_from_oca(), {"statements": 3, "moves": 0})
        self.assertRecordValues(
            Statement.search([("oca_id", "in", (10, 11, 12))], order="oca_id"),
            [
                {
                    "rate": 20.0,
                    "base_coeff": 1.0,
                    "gross_amount": 1000.0,
                    "taxable_amount": 1000.0,
                },
                {
                    "rate": 23.0,
                    "base_coeff": 0.5,
                    "gross_amount": 400.0,
                    "taxable_amount": 200.0,
                },
                {
                    "rate": 23.0,
                    "base_coeff": 0.5,
                    "gross_amount": 400.0,
                    "taxable_amount": 200.0,
                },
            ],
        )

    def test_import_wt_types(self):
        bill = self._bill()
        cr = self.env.cr
        self._create_oca_tables()
        cr.execute(
            """
            ALTER TABLE withholding_tax ADD COLUMN wt_types varchar;
            INSERT INTO withholding_tax
                   (id, code, name, payment_reason_id, company_id, wt_types)
            VALUES (1, '1040', 'Ritenuta 1040', NULL, %(c)s, 'ritenuta'),
                   (2, 'ENASARCO', 'Enasarco', NULL, %(c)s, 'enasarco');
            INSERT INTO withholding_tax_rate (withholding_tax_id, tax, base)
            VALUES (1, 20, 1), (2, 8.5, 1);
            INSERT INTO withholding_tax_statement VALUES
                (10, %(m)s, %(p)s, '2024-03-01', 1000, 200, 1, 'in'),
                (11, %(m)s, %(p)s, '2024-03-01', 1000, 85, 2, 'in');
            INSERT INTO withholding_tax_move VALUES
                (20, 10, %(p)s, '2024-04-01', 200, 'paid'),
                (21, 11, %(p)s, '2024-04-01', 85, 'paid');
            """,
            {"c": self.company.id, "m": bill.id, "p": self.partner_a.id},
        )
        Statement = self.env["withholding.history.statement"]
        self.assertEqual(Statement._import_from_oca(), {"statements": 2, "moves": 2})
        self.assertRecordValues(
            Statement.search([("oca_id", "in", (10, 11))], order="oca_id"),
            [{"oca_wt_types": "ritenuta"}, {"oca_wt_types": "enasarco"}],
        )
        self.assertRecordValues(
            self._register_rows(bill).sorted("amount"),
            [{"amount": 85.0, "irpef": False}, {"amount": 200.0, "irpef": True}],
        )
