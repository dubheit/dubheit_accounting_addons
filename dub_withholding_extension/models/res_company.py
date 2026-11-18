# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_it_wt_start_date = fields.Date(
        string="Withholding Register Start Date",
        help="Core withholding entries dated before this day stay out of the "
        "withholding register and of the F24 payments. Set it to the day the "
        "company switched to the core withholding taxes.",
    )
