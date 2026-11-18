# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models

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


    def init(self):
        self.env.cr.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "withholding_history_statement_oca_id_uniq "
            "ON withholding_history_statement (oca_id) WHERE oca_id > 0"
        )

    @api.depends("move_ids.amount")
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

    def init(self):
        self.env.cr.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "withholding_history_move_oca_id_uniq "
            "ON withholding_history_move (oca_id) WHERE oca_id > 0"
        )
