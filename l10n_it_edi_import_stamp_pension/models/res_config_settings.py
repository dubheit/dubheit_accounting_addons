from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_it_edi_stamp_purchase_product_id = fields.Many2one(
        related="company_id.l10n_it_edi_stamp_purchase_product_id",
        readonly=False,
        domain="[('company_id', 'in', [company_id, False])]",
    )
