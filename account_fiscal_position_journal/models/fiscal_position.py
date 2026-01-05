# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# Copyright 2025 Openindustry.it - Andrea M. Piovesana

from odoo import fields, models


class AccountFiscalPosition(models.Model):
    _inherit = "account.fiscal.position"
    _description = "Fiscal Position Default Journal"

    sale_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Sale Default Journal",
        domain="[('type', '=', 'sale'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    purchase_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Purchase Default Journal",
        domain="[('type', '=', 'purchase'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )