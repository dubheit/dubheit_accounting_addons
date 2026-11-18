# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class WithholdingPayment(models.Model):
    _name = "withholding.payment"
    _description = "Withholding Tax Payment (F24)"
    _order = "date desc, id desc"

    name = fields.Char(
        required=True,
        copy=False,
        default=lambda self: _("New"),
    )
    state = fields.Selection(
        [("draft", "Draft"), ("confirmed", "Confirmed")],
        default="draft",
        required=True,
        copy=False,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(related="company_id.currency_id")
    type_id = fields.Many2one(
        "withholding.payment.type",
        string="Payment Type",
        required=True,
    )
    date = fields.Date(
        string="Accounting Date",
        required=True,
        default=fields.Date.context_today,
    )
    date_payment = fields.Date(string="Payment Date")
    date_start = fields.Date(string="Period Start")
    date_stop = fields.Date(string="Period End")
    move_line_ids = fields.Many2many(
        "account.move.line",
        string="Withholding Lines",
        domain="[('reconciled', '=', False), ('parent_state', '=', 'posted')]",
        help="Unreconciled lines on the payable accounts to be paid.",
    )
    move_id = fields.Many2one(
        "account.move",
        string="Payment Entry",
        readonly=True,
        copy=False,
    )
    amount = fields.Monetary(
        compute="_compute_amount",
        store=True,
        currency_field="currency_id",
    )

    @api.depends("move_line_ids.balance")
    def _compute_amount(self):
        for rec in self:
            rec.amount = sum(-line.balance for line in rec.move_line_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("withholding.payment")
                    or _("New")
                )
        return super().create(vals_list)

    def action_load_lines(self):
        """Fill the lines with the due (unreconciled) lines of the type."""
        for rec in self:
            if not rec.type_id:
                raise UserError(_("Set the payment type first."))
            domain = [
                ("account_id", "in", rec.type_id.account_ids.ids),
                ("reconciled", "=", False),
                ("parent_state", "=", "posted"),
                ("company_id", "=", rec.company_id.id),
                ("balance", "!=", 0),
            ]
            start_date = rec.company_id.l10n_it_wt_start_date
            if start_date:
                domain.append(("date", ">=", start_date))
            if rec.date_start:
                domain.append(("date", ">=", rec.date_start))
            if rec.date_stop:
                domain.append(("date", "<=", rec.date_stop))
            lines = self.env["account.move.line"].search(domain)
            rec.move_line_ids = [(6, 0, lines.ids)]
        return True

    def action_confirm(self):
        for rec in self:
            rec._check_confirmable()
            move = rec._create_payment_move()
            rec._reconcile(move)
            rec.move_id = move.id
            rec.state = "confirmed"
        return True

    def _check_confirmable(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Only draft payments can be confirmed."))
        if not self.move_line_ids:
            raise UserError(_("No withholding lines to pay."))
        if any(line.reconciled for line in self.move_line_ids):
            raise UserError(
                _("Some selected lines are already reconciled. Reload the lines.")
            )
        wrong = self.move_line_ids.filtered(
            lambda line: line.account_id not in self.type_id.account_ids
        )
        if wrong:
            raise UserError(
                _(
                    "Some lines are on accounts not configured on the payment "
                    "type: %s",
                    ", ".join(wrong.account_id.mapped("code")),
                )
            )

    def _create_payment_move(self):
        self.ensure_one()
        move_lines = []
        total = 0.0
        # One debit line per payable account (to be reconciled with its dues)
        for account in self.move_line_ids.account_id:
            acc_lines = self.move_line_ids.filtered(
                lambda line: line.account_id == account
            )
            amount = sum(-line.balance for line in acc_lines)
            total += amount
            move_lines.append(
                (0, 0, {
                    "name": _("Withholding payment - %s", account.code),
                    "account_id": account.id,
                    "debit": amount if amount > 0 else 0.0,
                    "credit": -amount if amount < 0 else 0.0,
                })
            )
        # Counterpart (Erario c/versamenti or bank)
        move_lines.append(
            (0, 0, {
                "name": self.name,
                "account_id": self.type_id.counterpart_account_id.id,
                "debit": -total if total < 0 else 0.0,
                "credit": total if total > 0 else 0.0,
            })
        )
        move = self.env["account.move"].create({
            "journal_id": self.type_id.journal_id.id,
            "date": self.date,
            "ref": _("Withholding payment %s", self.name),
            "line_ids": move_lines,
        })
        move.action_post()
        return move

    def _reconcile(self, move):
        self.ensure_one()
        for account in self.move_line_ids.account_id:
            if not account.reconcile:
                continue
            due_lines = self.move_line_ids.filtered(
                lambda line: line.account_id == account
            )
            pay_line = move.line_ids.filtered(
                lambda line: line.account_id == account
            )
            (due_lines | pay_line).reconcile()

    def action_view_move(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.move_id.id,
            "view_mode": "form",
        }
