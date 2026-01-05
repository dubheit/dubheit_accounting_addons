# Copyright (C) 2025 Openindustry.it (https://openindustry.it).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _prepare_invoice(self):
        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        if self.partner_id.property_account_position_id.sale_journal_id:
            invoice_vals["journal_id"] = self.partner_id.property_account_position_id.sale_journal_id.id
        return invoice_vals
