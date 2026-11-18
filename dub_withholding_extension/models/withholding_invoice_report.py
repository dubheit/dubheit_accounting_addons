# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, tools
from odoo.tools import SQL

from .withholding_history import WT_KIND_SELECTION


class WithholdingInvoiceReport(models.Model):
    """Withholding register by invoice, with the paid and residual amounts.

    Core rows come from the withholding tax lines of the posted invoices (one
    row per invoice and tax), history rows from the imported OCA statements.
    Row ids: core = MIN(account.move.line id) * 2, history = statement id * 2 + 1.
    It reads l10n_it_withholding_tax_report, so it is created after it.
    """

    _name = "l10n_it.withholding.invoice.report"
    _description = "Withholding Register by Invoice"
    _auto = False
    _rec_name = "invoice_id"
    _order = "invoice_date desc, id desc"

    source = fields.Selection(
        [("core", "Odoo"), ("oca", "OCA history")], readonly=True
    )
    wt_kind = fields.Selection(WT_KIND_SELECTION, string="Kind", readonly=True)
    invoice_id = fields.Many2one("account.move", string="Invoice", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Partner", readonly=True)
    invoice_date = fields.Date(readonly=True)
    tax_id = fields.Many2one("account.tax", string="Withholding Tax", readonly=True)
    withholding_code = fields.Char(readonly=True)
    reason = fields.Char(readonly=True)
    gross_amount = fields.Monetary(readonly=True)
    taxable_amount = fields.Monetary(readonly=True)
    amount = fields.Monetary(string="Withholding", readonly=True)
    amount_paid = fields.Monetary(string="Withheld on Payments", readonly=True)
    amount_residual = fields.Monetary(string="Withheld Residual", readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            SQL(
                "CREATE OR REPLACE VIEW %s AS (%s UNION ALL %s)",
                SQL.identifier(self._table),
                self._query_core(),
                self._query_history(),
            )
        )

    def _query_core(self):
        """Withholding lines of the posted invoices and refunds.

        Same sign rule as the register by payment; the gross amount is
        negative for refunds. The paid amount is what the register by payment
        holds for the same invoice and tax.
        """
        return SQL(
            """
            SELECT MIN(aml.id) * 2 AS id, 'core' AS source,
                   CASE WHEN tax.type_tax_use = 'sale'
                        THEN 'suffered' ELSE 'operated' END AS wt_kind,
                   aml.move_id AS invoice_id,
                   am.commercial_partner_id AS partner_id,
                   am.invoice_date, aml.tax_line_id AS tax_id,
                   tax.l10n_it_withholding_type AS withholding_code,
                   tax.l10n_it_withholding_reason AS reason,
                   SUM(sgn.sign * ABS(aml.tax_base_amount)) AS gross_amount,
                   ROUND(SUM(sgn.sign * ABS(aml.tax_base_amount))
                         * tax.l10n_it_wt_base_percent::numeric / 100, 2)
                       AS taxable_amount,
                   SUM(CASE WHEN tax.type_tax_use = 'sale'
                            THEN aml.balance ELSE -aml.balance END) AS amount,
                   COALESCE(MAX(paid.amount), 0) AS amount_paid,
                   SUM(CASE WHEN tax.type_tax_use = 'sale'
                            THEN aml.balance ELSE -aml.balance END)
                       - COALESCE(MAX(paid.amount), 0) AS amount_residual,
                   aml.company_id, aml.company_currency_id AS currency_id
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            JOIN account_tax tax ON tax.id = aml.tax_line_id
            JOIN res_company comp ON comp.id = aml.company_id
            CROSS JOIN LATERAL (
                SELECT CASE WHEN am.move_type IN ('in_refund', 'out_refund')
                            THEN -1 ELSE 1 END AS sign
            ) sgn
            LEFT JOIN LATERAL (
                SELECT SUM(tr.amount) AS amount
                FROM l10n_it_withholding_tax_report tr
                WHERE tr.source = 'core'
                  AND tr.invoice_id = aml.move_id
                  AND tr.tax_id = aml.tax_line_id
            ) paid ON TRUE
            WHERE am.move_type IN ('in_invoice', 'in_refund',
                                   'out_invoice', 'out_refund')
              AND am.state = 'posted'
              AND tax.l10n_it_withholding_type IS NOT NULL
              AND (comp.l10n_it_wt_start_date IS NULL
                   OR am.date >= comp.l10n_it_wt_start_date)
            GROUP BY aml.move_id, aml.tax_line_id, am.commercial_partner_id,
                     am.invoice_date,
                     tax.type_tax_use, tax.l10n_it_withholding_type,
                     tax.l10n_it_withholding_reason, tax.l10n_it_wt_base_percent,
                     aml.company_id, aml.company_currency_id
            """
        )

    def _query_history(self):
        """OCA statements, paid amount from their payments."""
        return SQL(
            """
            SELECT hs.id * 2 + 1 AS id, 'oca' AS source, hs.wt_kind,
                   hs.invoice_id, hs.partner_id, hs.date AS invoice_date,
                   NULL::int AS tax_id, hs.withholding_code, hs.reason,
                   hs.gross_amount, hs.taxable_amount, hs.amount,
                   COALESCE(paid.amount, 0) AS amount_paid,
                   hs.amount - COALESCE(paid.amount, 0) AS amount_residual,
                   hs.company_id, comp.currency_id
            FROM withholding_history_statement hs
            JOIN res_company comp ON comp.id = hs.company_id
            LEFT JOIN LATERAL (
                SELECT SUM(hm.amount) AS amount
                FROM withholding_history_move hm
                WHERE hm.statement_id = hs.id
            ) paid ON TRUE
            """
        )
