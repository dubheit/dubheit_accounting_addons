# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_it_wt_start_date = fields.Date(
        related="company_id.l10n_it_wt_start_date",
        readonly=False,
    )
