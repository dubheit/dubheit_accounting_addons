# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountAccount(models.Model):
    _inherit = "account.account"

    l10n_it_wt_payment_type_ids = fields.Many2many(
        "withholding.payment.type",
        "wt_payment_type_account_rel",
        "account_id",
        "type_id",
        string="Withholding Payment Types",
    )
    l10n_it_wt_payable = fields.Boolean(
        string="Withholding Payable Account",
        compute="_compute_l10n_it_wt_payable",
        store=True,
        help="Set automatically when the account is used by a withholding "
        "payment type. Its unreconciled lines are amounts to be paid.",
    )

    @api.depends("l10n_it_wt_payment_type_ids")
    def _compute_l10n_it_wt_payable(self):
        for account in self:
            account.l10n_it_wt_payable = bool(account.l10n_it_wt_payment_type_ids)
