# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, tools
from odoo.tools import SQL

from .withholding_history import WT_KIND_SELECTION


class WithholdingTaxReport(models.Model):
    """Withholding register by payment.

    Core rows come from the withholding tax lines of the cash basis entries
    (one row per payment), history rows from the imported OCA payments.
    Row ids: core = account.move.line id * 2, history = history move id * 2 + 1.
    """

    _name = "l10n_it.withholding.tax.report"
    _description = "Withholding Register by Payment"
    _auto = False
    _order = "payment_date desc, id desc"

    source = fields.Selection(
        [("core", "Odoo"), ("oca", "OCA history")], readonly=True
    )
    wt_kind = fields.Selection(WT_KIND_SELECTION, string="Kind", readonly=True)
    move_line_id = fields.Many2one(
        "account.move.line", string="Journal Item", readonly=True
    )
    history_move_id = fields.Many2one(
        "withholding.history.move", string="OCA History Payment", readonly=True
    )
    invoice_id = fields.Many2one("account.move", string="Invoice", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Partner", readonly=True)
    partner_vat = fields.Char(related="partner_id.vat", string="VAT")
    partner_fiscalcode = fields.Char(
        related="partner_id.l10n_it_codice_fiscale", string="Fiscal Code"
    )
    payment_date = fields.Date(readonly=True)
    tax_id = fields.Many2one("account.tax", string="Withholding Tax", readonly=True)
    withholding_code = fields.Char(readonly=True)
    reason = fields.Char(readonly=True)
    amount = fields.Monetary(string="Withholding", readonly=True)
    gross_amount = fields.Monetary(readonly=True)
    taxable_amount = fields.Monetary(readonly=True)
    paid_f24 = fields.Boolean(string="Paid (F24)", readonly=True)
    withholding_payment_id = fields.Many2one(
        "withholding.payment", string="F24 Payment", readonly=True
    )
    f24_date = fields.Date(string="F24 Date", readonly=True)
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
        """Withholding lines of the posted, not reversed cash basis entries.

        The gross amount is the share of the invoice base paid by this entry:
        the cash basis line copies the whole invoice base in tax_base_amount.
        """
        return SQL(
            """
            SELECT aml.id * 2 AS id, 'core' AS source,
                   CASE WHEN tax.type_tax_use = 'sale'
                        THEN 'suffered' ELSE 'operated' END AS wt_kind,
                   aml.id AS move_line_id, NULL::int AS history_move_id,
                   caba.tax_cash_basis_origin_move_id AS invoice_id,
                   aml.partner_id,
                   caba.date AS payment_date, aml.tax_line_id AS tax_id,
                   tax.l10n_it_withholding_type AS withholding_code,
                   tax.l10n_it_withholding_reason AS reason,
                   amt.amount,
                   ROUND(ABS(aml.tax_base_amount) * amt.amount
                         / NULLIF(inv.total, 0), 2) AS gross_amount,
                   ROUND(ABS(aml.tax_base_amount) * amt.amount
                         / NULLIF(inv.total, 0)
                         * tax.l10n_it_wt_base_percent::numeric / 100, 2)
                       AS taxable_amount,
                   (f24.payment_id IS NOT NULL) AS paid_f24,
                   f24.payment_id AS withholding_payment_id,
                   f24.date AS f24_date,
                   aml.company_id, aml.company_currency_id AS currency_id
            FROM account_move_line aml
            JOIN account_move caba ON caba.id = aml.move_id
            JOIN account_tax tax ON tax.id = aml.tax_line_id
            JOIN res_company comp ON comp.id = aml.company_id
            CROSS JOIN LATERAL (
                SELECT CASE WHEN tax.type_tax_use = 'sale'
                            THEN aml.balance ELSE -aml.balance END AS amount
            ) amt
            CROSS JOIN LATERAL (
                SELECT ABS(SUM(il.balance)) AS total
                FROM account_move_line il
                WHERE il.move_id = caba.tax_cash_basis_origin_move_id
                  AND il.tax_repartition_line_id = aml.tax_repartition_line_id
            ) inv
            LEFT JOIN LATERAL (
                SELECT wp.id AS payment_id, wp.date
                FROM account_partial_reconcile apr
                JOIN account_move_line pl
                    ON pl.id IN (apr.debit_move_id, apr.credit_move_id)
                   AND pl.id <> aml.id
                JOIN withholding_payment wp
                    ON wp.move_id = pl.move_id AND wp.state = 'confirmed'
                WHERE aml.id IN (apr.debit_move_id, apr.credit_move_id)
                LIMIT 1
            ) f24 ON TRUE
            WHERE caba.tax_cash_basis_origin_move_id IS NOT NULL
              AND caba.state = 'posted'
              AND caba.reversed_entry_id IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM account_move r
                  WHERE r.reversed_entry_id = caba.id AND r.state = 'posted'
              )
              AND tax.l10n_it_withholding_type IS NOT NULL
              AND (comp.l10n_it_wt_start_date IS NULL
                   OR caba.date >= comp.l10n_it_wt_start_date)
            """
        )

    def _query_history(self):
        """Payments of the OCA history, gross and taxable in proportion."""
        return SQL(
            """
            SELECT hm.id * 2 + 1 AS id, 'oca' AS source, hs.wt_kind,
                   NULL::int AS move_line_id, hm.id AS history_move_id,
                   hs.invoice_id, hm.partner_id,
                   hm.date AS payment_date, NULL::int AS tax_id,
                   hs.withholding_code, hs.reason,
                   hm.amount,
                   ROUND(hm.amount * hs.gross_amount
                         / NULLIF(hs.amount, 0), 2) AS gross_amount,
                   ROUND(hm.amount * hs.taxable_amount
                         / NULLIF(hs.amount, 0), 2) AS taxable_amount,
                   COALESCE(hm.state = 'paid', FALSE) AS paid_f24,
                   NULL::int AS withholding_payment_id,
                   NULL::date AS f24_date,
                   hm.company_id, comp.currency_id
            FROM withholding_history_move hm
            JOIN withholding_history_statement hs ON hs.id = hm.statement_id
            JOIN res_company comp ON comp.id = hm.company_id
            """
        )
