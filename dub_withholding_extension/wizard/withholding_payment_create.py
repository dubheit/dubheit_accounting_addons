# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, fields, models
from odoo.exceptions import UserError


class WithholdingPaymentCreate(models.TransientModel):
    _name = "withholding.payment.create"
    _description = "Create Withholding Payment from Lines"

    def _default_lines(self):
        ctx = self.env.context
        model = ctx.get("active_model")
        active_ids = ctx.get("active_ids", [])
        if model == "account.move.line":
            return [(6, 0, active_ids)]
        if model == "l10n_it.withholding.tax.report":
            report = self.env[model].browse(active_ids)
            return [(6, 0, report.mapped("move_line_id").ids)]
        return False

    type_id = fields.Many2one(
        "withholding.payment.type", string="Payment Type", required=True
    )
    date = fields.Date(required=True, default=fields.Date.context_today)
    line_ids = fields.Many2many(
        "account.move.line", string="Withholding Lines", default=_default_lines
    )

    def action_create(self):
        self.ensure_one()
        lines = self.line_ids.filtered(lambda line: not line.reconciled)
        if not lines:
            raise UserError(_("No unreconciled lines selected."))
        payment = self.env["withholding.payment"].create({
            "type_id": self.type_id.id,
            "date": self.date,
            "move_line_ids": [(6, 0, lines.ids)],
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "withholding.payment",
            "res_id": payment.id,
            "view_mode": "form",
            "target": "current",
        }
