# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# Copyright 2025 Openindustry.it - Andrea M. Piovesana

from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.depends("fiscal_position_id")
    def _compute_journal_id(self):
        res = super()._compute_journal_id()
        for move in self.filtered(
            lambda m: m.fiscal_position_id.sale_journal_id
            and m.move_type in ["out_invoice", "out_refund", "out_receipt"]
        ):
            move.journal_id = move.fiscal_position_id.sale_journal_id
        for move in self.filtered(
            lambda m: m.fiscal_position_id.purchase_journal_id
            and m.move_type in ["in_invoice", "in_refund", "in_receipt"]
        ):
            move.journal_id = move.fiscal_position_id.purchase_journal_id
        return res
