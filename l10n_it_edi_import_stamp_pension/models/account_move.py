import re

from odoo import Command, _, api, models
from odoo.tools import float_compare

from odoo.addons.l10n_it_edi.models.account_move import get_float, get_text

# Fields that mark a tax as pension fund or withholding: the core uses them to
# search those taxes, never to search the VAT of a line.
NON_VAT_TAX_FIELDS = ("l10n_it_pension_fund_type", "l10n_it_withholding_type")

# Legal stamp duty on invoices, used when the XML says BolloVirtuale SI without
# ImportoBollo (optional in the FatturaPA schema).
STAMP_DUTY_LEGAL_AMOUNT = 2.0


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_it_edi_search_tax_for_import(
        self, company, percentage, extra_domain=None, l10n_it_exempt_reason=None
    ):
        # The core VAT search matches type, percentage and exemption reason
        # only, so a 4% pension fund tax with a lower sequence (the standard
        # "4% INPS") wins over the 4% VAT. Exclude pension fund and withholding
        # taxes unless the caller is searching for one of them.
        searched_fields = {
            leaf[0] for leaf in (extra_domain or []) if isinstance(leaf, (list, tuple))
        }
        if not searched_fields.intersection(NON_VAT_TAX_FIELDS):
            extra_domain = list(extra_domain or []) + [
                (field, "=", False) for field in NON_VAT_TAX_FIELDS
            ]
        return super()._l10n_it_edi_search_tax_for_import(
            company,
            percentage,
            extra_domain=extra_domain,
            l10n_it_exempt_reason=l10n_it_exempt_reason,
        )

    def _l10n_it_edi_import_invoice(self, invoice, data, is_new):
        move = super()._l10n_it_edi_import_invoice(invoice, data, is_new)
        if move:
            move._l10n_it_edi_add_stamp_duty_line(data["xml_tree"])
        return move

    def _l10n_it_edi_add_stamp_duty_line(self, xml_tree):
        """Add the stamp duty as a bill line when the supplier charges it.

        The core only stores the stamp duty in the informational field
        l10n_it_stamp_duty. The supplier charges it when the amount to pay
        (ImportoPagamento) exceeds the bill total by exactly the stamp duty;
        when it is already a line, or not charged, the difference is zero.
        """
        self.ensure_one()
        body = xml_tree.find(".//FatturaElettronicaBody")
        if self.move_type not in ("in_invoice", "in_refund") or body is None:
            return
        stamp_duty = self.l10n_it_stamp_duty
        if not stamp_duty and get_text(body, ".//DatiGeneraliDocumento/DatiBollo/BolloVirtuale").upper() == "SI":
            stamp_duty = STAMP_DUTY_LEGAL_AMOUNT
        product = self.company_id.l10n_it_edi_stamp_purchase_product_id
        if product.company_id and product.company_id not in self.company_id.parent_ids:
            # A product of another company cannot go on this bill
            product = product.browse()
        if not stamp_duty or (product and product in self.invoice_line_ids.product_id):
            return
        amounts_to_pay = get_text(body, ".//ImportoPagamento", many=True)
        if not amounts_to_pay:
            return
        difference = sum(float(amount) for amount in amounts_to_pay if amount) - self.amount_total
        if self.currency_id.compare_amounts(difference, stamp_duty) != 0:
            return
        if not product:
            self.message_post(
                body=_(
                    "Stamp duty of %(amount)s not added: set the stamp duty product "
                    "in the Italian Electronic Invoicing settings.",
                    amount=stamp_duty,
                )
            )
            return
        self.invoice_line_ids = [
            Command.create({"product_id": product.id, "quantity": 1, "price_unit": stamp_duty})
        ]

    def _l10n_it_edi_get_extra_info(self, company, document_type, body_tree, incoming=True):
        extra_info, message_to_log = super()._l10n_it_edi_get_extra_info(
            company, document_type, body_tree, incoming=incoming
        )
        # Natura of each pension fund by VAT rate, for the 0% backport below:
        # the newer core matches it too, so a 0% line with another Natura (for
        # example the stamp duty, N1) does not get the pension fund.
        extra_info["l10n_it_edi_pension_fund_naturas"] = {
            get_float(element, "AliquotaIVA"): get_text(element, "Natura") or False
            for element in body_tree.xpath(".//DatiGeneraliDocumento/DatiCassaPrevidenziale")
        }
        return extra_info, message_to_log

    @api.model
    def _get_pension_fund_tax_for_line(self, element, extra_info):
        # Backport: the Odoo 19 builds before September 2026 skip the pension
        # fund on 0% lines, which is how flat-rate suppliers send it. They key
        # the pension fund map by VAT rate (float); newer builds key it by
        # (rate, Natura) and already find the tax in super, so this does
        # nothing there. Remove once every installation runs a newer core.
        pension_fund_tax = super()._get_pension_fund_tax_for_line(element, extra_info)
        line_natura = get_text(element, ".//Natura")
        if pension_fund_tax or get_float(element, ".//AliquotaIVA") or not line_natura:
            return pension_fund_tax
        if extra_info.get("l10n_it_edi_pension_fund_naturas", {}).get(0.0) != line_natura:
            return None
        pension_fund_tax = extra_info.get("pension_fund_taxes", {}).get(0.0)
        if not pension_fund_tax:
            return None
        if not extra_info.get("pension_fund_assosoftware_tags"):
            return pension_fund_tax
        # Same AssoSoftware 'AswCassPre' check as the core
        selector = ".//AltriDatiGestionali[TipoDato[contains(text(),'AswCassPre')]]/RiferimentoTesto"
        reference_text = get_text(element, selector)
        match = reference_text and re.match(r"(?P<kind>TC\d{2}) \((?P<tax_rate>\d+)%\)", reference_text)
        if (
            match
            and match.group("kind") == pension_fund_tax.l10n_it_pension_fund_type
            and float_compare(float(match.group("tax_rate")), pension_fund_tax.amount, precision_digits=2) == 0
        ):
            return pension_fund_tax
        return None
