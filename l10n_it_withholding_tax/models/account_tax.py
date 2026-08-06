# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


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
