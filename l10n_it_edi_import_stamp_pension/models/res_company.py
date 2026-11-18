from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_it_edi_stamp_purchase_product_id = fields.Many2one(
        comodel_name="product.product",
        string="Stamp Duty Product (Vendor Bills)",
        help="Product used for the stamp duty line added to imported vendor bills "
        "when the supplier charges it. Its expense account and purchase taxes "
        "are used on the line.",
    )
