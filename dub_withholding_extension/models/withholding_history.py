# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models

WT_KIND_SELECTION = [("operated", "Operated"), ("suffered", "Suffered")]


class WithholdingHistoryStatement(models.Model):
    _name = "withholding.history.statement"
    _description = "Withholding History Statement"
    _order = "date desc, id desc"

    oca_id = fields.Integer(string="OCA ID", index=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(related="company_id.currency_id")
    invoice_id = fields.Many2one("account.move", string="Invoice")
    partner_id = fields.Many2one("res.partner", required=True)
    date = fields.Date(required=True)
    wt_kind = fields.Selection(WT_KIND_SELECTION, string="Kind", required=True)
    withholding_code = fields.Char()
    withholding_name = fields.Char()
    reason = fields.Char()
    rate = fields.Float()
    base_coeff = fields.Float()
    gross_amount = fields.Monetary()
    taxable_amount = fields.Monetary()
    amount = fields.Monetary()
    move_ids = fields.One2many(
        "withholding.history.move", "statement_id", string="Payments"
    )
    amount_paid = fields.Monetary(compute="_compute_amount_paid")

    _sql_constraints = [
        ("oca_id_unique", "unique(oca_id)", "The OCA ID must be unique."),
    ]

    def _compute_amount_paid(self):
        for statement in self:
            statement.amount_paid = sum(statement.move_ids.mapped("amount"))


class WithholdingHistoryMove(models.Model):
    _name = "withholding.history.move"
    _description = "Withholding History Payment"
    _order = "date, id"

    oca_id = fields.Integer(string="OCA ID", index=True)
    statement_id = fields.Many2one(
        "withholding.history.statement",
        required=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        related="statement_id.company_id", store=True, index=True
    )
    currency_id = fields.Many2one(related="statement_id.currency_id")
    partner_id = fields.Many2one("res.partner", required=True)
    date = fields.Date(required=True)
    amount = fields.Monetary()
    state = fields.Selection(
        [("due", "To Pay"), ("paid", "Paid (OCA data)")],
        default="due",
    )

    _sql_constraints = [
        ("oca_id_unique", "unique(oca_id)", "The OCA ID must be unique."),
    ]
