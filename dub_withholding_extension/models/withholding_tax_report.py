# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, tools


class WithholdingTaxReport(models.Model):
    _name = "l10n_it.withholding.tax.report"
    _description = "Withholding Taxes to Pay"
    _auto = False
    _rec_name = "move_name"
    _order = "payment_date desc, move_name"

    move_line_id = fields.Many2one(
        "account.move.line", string="Journal Item", readonly=True
    )
    move_id = fields.Many2one("account.move", string="Document", readonly=True)
    move_name = fields.Char(string="Document Number", readonly=True)
    ref = fields.Char(string="Supplier Reference", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Supplier", readonly=True)
    tax_line_id = fields.Many2one(
        "account.tax", string="Withholding Type", readonly=True
    )
    account_id = fields.Many2one(
        "account.account", string="Payable Account", readonly=True
    )
    invoice_date = fields.Date(string="Document Date", readonly=True)
    date = fields.Date(string="Accounting Date", readonly=True)
    payment_date = fields.Date(string="Supplier Payment Date", readonly=True)
    amount_due = fields.Monetary(string="Amount to Pay", readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    reconciled = fields.Boolean(string="Paid (F24)", readonly=True)
    supplier_paid = fields.Boolean(
        string="Supplier Paid", readonly=True,
        help="True when the source document has been paid to the supplier, "
        "which triggers the obligation to pay the withholding.",
    )
    parent_state = fields.Selection(
        [("draft", "Draft"), ("posted", "Posted"), ("cancel", "Cancelled")],
        string="Status",
        readonly=True,
    )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            """
            CREATE VIEW %s AS (
                SELECT
                    aml.id                       AS id,
                    aml.id                       AS move_line_id,
                    aml.move_id                  AS move_id,
                    am.name                      AS move_name,
                    am.ref                       AS ref,
                    aml.partner_id               AS partner_id,
                    aml.tax_line_id              AS tax_line_id,
                    aml.account_id               AS account_id,
                    am.invoice_date              AS invoice_date,
                    aml.date                     AS date,
                    (-aml.balance)               AS amount_due,
                    aml.currency_id              AS currency_id,
                    aml.company_id               AS company_id,
                    aml.reconciled               AS reconciled,
                    am.state                     AS parent_state,
                    pay.payment_date             AS payment_date,
                    (pay.payment_date IS NOT NULL) AS supplier_paid
                FROM account_move_line aml
                JOIN account_move am ON am.id = aml.move_id
                JOIN account_account acc ON acc.id = aml.account_id
                LEFT JOIN LATERAL (
                    SELECT max(cp.date) AS payment_date
                    FROM account_partial_reconcile apr
                    JOIN account_move_line term
                        ON term.id IN (apr.debit_move_id, apr.credit_move_id)
                       AND term.move_id = am.id
                    JOIN account_account ta
                        ON ta.id = term.account_id
                       AND ta.account_type IN (
                           'liability_payable', 'asset_receivable')
                    JOIN account_move_line cp
                        ON cp.id IN (apr.debit_move_id, apr.credit_move_id)
                       AND cp.id <> term.id
                ) pay ON TRUE
                WHERE acc.l10n_it_wt_payable = TRUE
                  AND aml.tax_line_id IS NOT NULL
            )
            """
            % (self._table,)
        )
