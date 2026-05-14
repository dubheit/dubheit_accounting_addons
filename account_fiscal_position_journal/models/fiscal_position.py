# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# Copyright 2025 Openindustry.it - Andrea M. Piovesana

from odoo import fields, models


class AccountFiscalPosition(models.Model):
    _inherit = "account.fiscal.position"

    sale_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Default Sale Journal",
        help="Sales journal used by default on customer invoices and refunds "
             "when this fiscal position applies.",
        domain="[('type', '=', 'sale'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    purchase_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Default Purchase Journal",
        help="Purchase journal used by default on vendor bills and refunds "
             "when this fiscal position applies.",
        domain="[('type', '=', 'purchase'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )