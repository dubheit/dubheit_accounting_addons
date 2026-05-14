import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    dub_3way_exception_summary = fields.Text(
        compute="_compute_dub_3way_exception_summary",
    )

    @api.depends(
        "release_to_pay",
        "invoice_line_ids.can_be_paid",
        "invoice_line_ids.quantity",
        "invoice_line_ids.purchase_line_id",
    )
    def _compute_dub_3way_exception_summary(self):
        for move in self:
            move.dub_3way_exception_summary = False
            if move.release_to_pay != "exception":
                continue
            if move.move_type not in ("in_invoice", "in_refund"):
                continue
            rows = []
            for line in move.invoice_line_ids:
                if line.display_type != "product":
                    continue
                if line.can_be_paid != "exception":
                    continue
                product_label = (
                    line.product_id.display_name or line.name or _("Line")
                )
                pol = line.purchase_line_id
                if not pol:
                    rows.append(_(
                        "%(product)s: invoice line not linked to any "
                        "purchase order",
                        product=product_label,
                    ))
                    continue
                invoiced = line.quantity
                ordered = pol.product_qty
                received = pol.qty_received
                po_name = pol.order_id.name
                if pol.product_id.purchase_method == "purchase":
                    rows.append(_(
                        "%(product)s: invoiced %(inv).2f vs ordered "
                        "%(ord).2f (Δ %(diff)+.2f) — %(po)s",
                        product=product_label,
                        inv=invoiced,
                        ord=ordered,
                        diff=invoiced - ordered,
                        po=po_name,
                    ))
                else:
                    rows.append(_(
                        "%(product)s: invoiced %(inv).2f vs received "
                        "%(rec).2f (Δ %(diff)+.2f) — %(po)s",
                        product=product_label,
                        inv=invoiced,
                        rec=received,
                        diff=invoiced - received,
                        po=po_name,
                    ))
            move.dub_3way_exception_summary = "\n".join(rows) or False

    def _l10n_it_edi_import_invoice(self, invoice, data, is_new):
        result = super()._l10n_it_edi_import_invoice(invoice, data, is_new)
        if result:
            result._dub_3way_match_auto_link_po()
        return result

    def _dub_3way_match_auto_link_po(self):
        self.ensure_one()
        if self.move_type not in ("in_invoice", "in_refund"):
            return
        if not self.partner_id:
            return

        partner = self.partner_id.commercial_partner_id or self.partner_id
        linked = 0
        for line in self.invoice_line_ids:
            if line.display_type != "product" or line.purchase_line_id \
                    or not line.product_id:
                continue
            candidates = line._dub_3way_match_find_po_line_candidates(partner)
            if len(candidates) == 1:
                line.purchase_line_id = candidates.id
                linked += 1

        if linked:
            _logger.info(
                "dub_3way_match: linked %s invoice line(s) to PO lines on move %s",
                linked,
                self.display_name,
            )


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _dub_3way_match_find_po_line_candidates(self, partner):
        """Return open purchase.order.line records that could match this bill line.

        A candidate is an order line of the given vendor and product, in an
        active PO state, with residual quantity to invoice. The caller decides
        what to do when more than one candidate is returned (typically: skip
        and let the user pick via the Purchase Matching view).
        """
        self.ensure_one()
        po_lines = self.env["purchase.order.line"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("order_id.partner_id", "child_of", partner.id),
                ("order_id.state", "in", ("purchase", "done")),
                ("product_id", "=", self.product_id.id),
            ]
        )
        return po_lines.filtered(lambda pol: pol.qty_to_invoice > 0)
