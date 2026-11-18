# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import api, fields, models
from odoo.tools import SQL
from odoo.tools.sql import column_exists, table_exists

_logger = logging.getLogger(__name__)

WT_KIND_SELECTION = [("operated", "Operated"), ("suffered", "Suffered")]


def oca_gross_taxable(base, tax, rate, coeff):
    """Return (gross, taxable) from an OCA statement.

    OCA stores a single ``base``: usually the taxable amount, sometimes the
    gross one. The row is decided by comparing the withholding ``tax`` with
    the rate (cent precision).
    """
    coeff = coeff or 1.0
    if not rate:
        return base, base
    # OCA computed round(base * (rate / 100), 2): compare with half-cent tolerance
    tolerance = 0.005 + 1e-9
    if abs(base * rate / 100 - tax) <= tolerance:
        return round(base / coeff, 2), base
    taxable = round(base * coeff, 2)
    if abs(taxable * rate / 100 - tax) <= tolerance:
        return base, taxable
    taxable = round(tax * 100 / rate, 2)
    return round(taxable / coeff, 2), taxable


class WithholdingHistoryStatement(models.Model):
    _name = "withholding.history.statement"
    _description = "Withholding History Statement"
    _order = "date desc, id desc"

    oca_id = fields.Integer(string="OCA ID", index=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(related="company_id.currency_id")
    invoice_id = fields.Many2one("account.move", string="Invoice")
    partner_id = fields.Many2one("res.partner", required=True)
    date = fields.Date(required=True)
    wt_kind = fields.Selection(WT_KIND_SELECTION, string="Kind", required=True)
    withholding_code = fields.Char()
    withholding_name = fields.Char()
    reason = fields.Char()
    oca_wt_types = fields.Char(
        string="OCA Withholding Type",
        help="Type of the OCA withholding tax (ritenuta, enasarco, inps, enpam, "
        "other). Empty or 'ritenuta' means an IRPEF withholding, the only kind "
        "in the CU summary.",
    )
    rate = fields.Float()
    base_coeff = fields.Float()
    gross_amount = fields.Monetary()
    taxable_amount = fields.Monetary()
    amount = fields.Monetary()
    move_ids = fields.One2many(
        "withholding.history.move", "statement_id", string="Payments"
    )
    amount_paid = fields.Monetary(compute="_compute_amount_paid")

    def init(self):
        self.env.cr.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "withholding_history_statement_oca_id_uniq "
            "ON withholding_history_statement (oca_id) WHERE oca_id > 0"
        )

    @api.model
    def _import_from_oca(self):
        """Import OCA statements and payments not imported yet.

        Idempotent on the positive ``oca_id``; OCA tables are left untouched.
        :return: dict with the number of imported ``statements`` and ``moves``
        """
        cr = self.env.cr
        result = {"statements": 0, "moves": 0}
        if not table_exists(cr, "withholding_tax_statement"):
            return result
        self.env.flush_all()
        reason_join = SQL("")
        reason_col = SQL("NULL")
        for table, column in (
            ("payment_reason", "payment_reason_id"),
            ("causale_pagamento", "causale_pagamento_id"),
        ):
            if table_exists(cr, table) and column_exists(
                cr, "withholding_tax", column
            ):
                reason_join = SQL(
                    "LEFT JOIN %s pr ON pr.id = wt.%s",
                    SQL.identifier(table),
                    SQL.identifier(column),
                )
                reason_col = SQL("pr.code")
                break
        wt_types_col = SQL("NULL")
        if column_exists(cr, "withholding_tax", "wt_types"):
            wt_types_col = SQL("wt.wt_types")
        cr.execute(
            SQL(
                """
                SELECT s.id, am.id AS invoice_id,
                       COALESCE(s.partner_id, am.partner_id) AS partner_id,
                       COALESCE(s.date, am.date) AS date,
                       s.base, s.tax, s.wt_type, wt.code, wt.name,
                       %(reason_col)s AS reason,
                       %(wt_types_col)s AS wt_types,
                       COALESCE(am.company_id, wt.company_id) AS company_id,
                       rt.tax AS rate, rt.base AS coeff
                  FROM withholding_tax_statement s
                  LEFT JOIN account_move am ON am.id = s.move_id
                  LEFT JOIN withholding_tax wt ON wt.id = s.withholding_tax_id
                  %(reason_join)s
                  LEFT JOIN LATERAL (
                        SELECT r.tax, r.base
                          FROM withholding_tax_rate r
                         WHERE r.withholding_tax_id = s.withholding_tax_id
                         ORDER BY (
                                (r.date_start IS NULL
                                 OR r.date_start <= COALESCE(s.date, am.date))
                                AND (r.date_stop IS NULL
                                 OR r.date_stop >= COALESCE(s.date, am.date))
                               ) DESC,
                               r.date_start DESC NULLS LAST, r.id DESC
                         LIMIT 1) rt ON TRUE
                 WHERE s.id NOT IN (
                        SELECT oca_id FROM withholding_history_statement
                         WHERE oca_id > 0)
                 ORDER BY s.id
                """,
                reason_col=reason_col,
                reason_join=reason_join,
                wt_types_col=wt_types_col,
            )
        )
        rows = cr.dictfetchall()
        vals_list = []
        skipped = 0
        for row in rows:
            if not row["partner_id"] or not row["date"]:
                skipped += 1
                continue
            rate = row["rate"] or 0.0
            coeff = row["coeff"] or 1.0
            gross, taxable = oca_gross_taxable(
                row["base"] or 0.0, row["tax"] or 0.0, rate, coeff
            )
            vals_list.append(
                {
                    "oca_id": row["id"],
                    "company_id": row["company_id"] or self.env.company.id,
                    "invoice_id": row["invoice_id"] or False,
                    "partner_id": row["partner_id"],
                    "date": row["date"],
                    "wt_kind": "suffered" if row["wt_type"] == "out" else "operated",
                    "withholding_code": row["code"],
                    "withholding_name": row["name"],
                    "reason": row["reason"],
                    "oca_wt_types": row["wt_types"],
                    "rate": rate,
                    "base_coeff": coeff,
                    "gross_amount": gross,
                    "taxable_amount": taxable,
                    "amount": row["tax"] or 0.0,
                }
            )
        statements = self.create(vals_list)
        by_oca_id = {st.oca_id: st for st in statements}
        result["statements"] = len(statements)

        if by_oca_id:
            cr.execute(
                """
                SELECT m.id, m.statement_id,
                       COALESCE(m.partner_id, s.partner_id, am.partner_id)
                           AS partner_id,
                       m.date, m.amount, m.state
                  FROM withholding_tax_move m
                  JOIN withholding_tax_statement s ON s.id = m.statement_id
                  LEFT JOIN account_move am ON am.id = s.move_id
                 WHERE m.statement_id IN %s
                   AND m.id NOT IN (
                        SELECT oca_id FROM withholding_history_move
                         WHERE oca_id > 0)
                 ORDER BY m.id
                """,
                (tuple(by_oca_id),),
            )
            move_vals = []
            for row in cr.dictfetchall():
                if not row["partner_id"] or not row["date"]:
                    skipped += 1
                    continue
                move_vals.append(
                    {
                        "oca_id": row["id"],
                        "statement_id": by_oca_id[row["statement_id"]].id,
                        "partner_id": row["partner_id"],
                        "date": row["date"],
                        "amount": row["amount"] or 0.0,
                        "state": "paid" if row["state"] == "paid" else "due",
                    }
                )
            moves = self.env["withholding.history.move"].create(move_vals)
            result["moves"] = len(moves)

        _logger.info(
            "OCA withholding history: read %s statements, imported %s statements "
            "and %s moves, skipped %s (missing partner or date)",
            len(rows),
            result["statements"],
            result["moves"],
            skipped,
        )
        return result

    @api.depends("move_ids.amount")
    def _compute_amount_paid(self):
        for statement in self:
            statement.amount_paid = sum(statement.move_ids.mapped("amount"))


class WithholdingHistoryMove(models.Model):
    _name = "withholding.history.move"
    _description = "Withholding History Payment"
    _order = "date, id"

    oca_id = fields.Integer(string="OCA ID", index=True)
    statement_id = fields.Many2one(
        "withholding.history.statement",
        required=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        related="statement_id.company_id", store=True, index=True
    )
    currency_id = fields.Many2one(related="statement_id.currency_id")
    partner_id = fields.Many2one("res.partner", required=True)
    date = fields.Date(required=True)
    amount = fields.Monetary()
    state = fields.Selection(
        [("due", "To Pay"), ("paid", "Paid (OCA data)")],
        default="due",
    )

    def init(self):
        self.env.cr.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "withholding_history_move_oca_id_uniq "
            "ON withholding_history_move (oca_id) WHERE oca_id > 0"
        )
