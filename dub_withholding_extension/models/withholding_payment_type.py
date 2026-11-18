# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class WithholdingPaymentType(models.Model):
    _name = "withholding.payment.type"
    _inherit = ["mail.thread"]
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

    l10n_it_wt_config_warning = fields.Char(
        string="Configuration Warning",
        compute="_compute_l10n_it_wt_config_warning",
    )

    @api.depends("tax_ids.tax_exigibility", "company_id.tax_exigibility")
    def _compute_l10n_it_wt_config_warning(self):
        for rec in self:
            warning = False
            if not rec.company_id.tax_exigibility:
                warning = _(
                    "Cash basis taxes are not enabled on the company: "
                    "withholding taxes are not recorded on payment."
                )
            elif any(tax.tax_exigibility != "on_payment" for tax in rec.tax_ids):
                warning = _(
                    "Some taxes are not due on payment: the withholding is "
                    "not supported unless the taxes are cash basis."
                )
            rec.l10n_it_wt_config_warning = warning

    @api.depends("tax_ids")
    def _compute_account_ids(self):
        for rec in self:
            accounts = self.env["account.account"]
            for tax in rec.tax_ids:
                accounts |= tax.invoice_repartition_line_ids.filtered(
                    lambda line: line.repartition_type == "tax"
                    and line.account_id
                ).account_id
            rec.account_ids = [(6, 0, accounts.ids)]

    def _l10n_it_wt_make_accounts_reconcilable(self):
        """Make the payable accounts reconcilable, so the F24 can be matched
        with the amounts due (the core template account is not reconcilable)."""
        for rec in self:
            for account in rec.account_ids.filtered(lambda acc: not acc.reconcile):
                account.reconcile = True
                rec.message_post(
                    body=_(
                        "Account %s made reconcilable to pay the withholding.",
                        account.display_name,
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._l10n_it_wt_make_accounts_reconcilable()
        return records

    def write(self, vals):
        res = super().write(vals)
        if "tax_ids" in vals or "account_ids" in vals:
            self._l10n_it_wt_make_accounts_reconcilable()
        return res
