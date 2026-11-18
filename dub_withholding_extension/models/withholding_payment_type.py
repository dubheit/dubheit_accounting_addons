# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class WithholdingPaymentType(models.Model):
    _name = "withholding.payment.type"
    _description = "Withholding Payment Type"

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    tax_ids = fields.Many2many(
        "account.tax",
        "wt_payment_type_tax_rel",
        "type_id",
        "tax_id",
        string="Withholding Taxes",
        required=True,
        domain="['|', ('l10n_it_withholding_type', '!=', False),"
        " ('l10n_it_pension_fund_type', '!=', False)]",
        help="Withholding / social security taxes (ritenute d'acconto, "
        "ENASARCO, cassa previdenziale) managed by this payment type. The "
        "payable accounts are derived from their tax repartition.",
    )
    account_ids = fields.Many2many(
        "account.account",
        "wt_payment_type_account_rel",
        "type_id",
        "account_id",
        string="Payable Accounts",
        compute="_compute_account_ids",
        store=True,
        readonly=False,
        help="Accounts that accumulate the amounts to be paid, derived from "
        "the selected taxes. Their unreconciled lines are the amounts due. "
        "You may override them if needed.",
    )
    codice_tributo = fields.Char(string="F24 Tax Code")
    journal_id = fields.Many2one(
        "account.journal",
        string="Payment Journal",
        required=True,
        help="Journal used to book the payment (F24) entry.",
    )
    counterpart_account_id = fields.Many2one(
        "account.account",
        string="Counterpart Account",
        required=True,
        help="Account credited when the withholding taxes are paid "
        "(e.g. Erario c/versamenti or the bank account).",
    )

    @api.depends("tax_ids")
    def _compute_account_ids(self):
        for rec in self:
            accounts = self.env["account.account"]
            for tax in rec.tax_ids:
                accounts |= tax.invoice_repartition_line_ids.filtered(
                    lambda line: line.repartition_type == "tax"
                    and line.account_id
                    and line.account_id.reconcile
                ).account_id
            rec.account_ids = [(6, 0, accounts.ids)]
