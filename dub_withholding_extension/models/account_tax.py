# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.tools import float_compare


class AccountTax(models.Model):
    _inherit = "account.tax"

    l10n_it_wt_company_tax_id = fields.Many2one(
        "account.tax",
        string="Company-charge Tax",
        help="Tax charged to the company that is automatically added to a line "
        "whenever this withholding tax is applied (e.g. the ENASARCO company "
        "quota paired with the agent ENASARCO withholding). It is typically a "
        "reverse-charge tax, so it does not change the invoice total.",
    )
    l10n_it_wt_base_percent = fields.Float(
        string="Taxable Base %",
        digits=(5, 2),
        compute="_compute_l10n_it_wt_base_percent",
        store=True,
        readonly=False,
        tracking=True,
        help="Percentage of the amount subject to withholding that makes up the "
        "taxable base. Core withholding taxes only carry the effective rate "
        "(e.g. 11.5% = 23% on 50%), while the CU needs the taxable amount.",
    )

    @api.depends("amount", "l10n_it_withholding_type")
    def _compute_l10n_it_wt_base_percent(self):
        for tax in self:
            percent = 100.0
            if tax.l10n_it_withholding_type:
                if float_compare(tax.amount, -11.5, precision_digits=2) == 0:
                    percent = 50.0
                elif float_compare(tax.amount, -4.6, precision_digits=2) == 0:
                    percent = 20.0
            tax.l10n_it_wt_base_percent = percent
