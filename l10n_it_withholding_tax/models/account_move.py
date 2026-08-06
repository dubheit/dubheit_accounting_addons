# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _l10n_it_wt_add_company_taxes(self):
        """Add the paired company-charge tax to any base line carrying a
        withholding tax that defines one (e.g. ENASARCO company quota next to
        the agent ENASARCO withholding). Only on draft vendor documents."""
        for line in self:
            move = line.move_id
            if not move or move.state != "draft":
                continue
            if move.move_type not in ("in_invoice", "in_refund"):
                continue
            if line.tax_line_id or line.display_type not in ("product", False):
                continue
            company_taxes = line.tax_ids.mapped(
                "l10n_it_wt_company_tax_id"
            ).filtered(lambda tax: tax and tax not in line.tax_ids)
            if company_taxes:
                line.with_context(l10n_it_wt_skip=True).tax_ids = [
                    (4, tax.id) for tax in company_taxes
                ]

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if not self.env.context.get("l10n_it_wt_skip"):
            lines._l10n_it_wt_add_company_taxes()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("l10n_it_wt_skip") and "tax_ids" in vals:
            self._l10n_it_wt_add_company_taxes()
        return res
