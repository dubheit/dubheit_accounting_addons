# Copyright (C) 2023 Openindustry.it (https://openindustry.it).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def _prepare_invoice(self):
        invoice_vals = super(PurchaseOrder, self)._prepare_invoice()
        if self.partner_id.property_account_position_id.purchase_journal_id:
            invoice_vals["journal_id"] = self.partner_id.property_account_position_id.purchase_journal_id.id
        return invoice_vals
