from lxml import etree

from odoo.tests import tagged
from odoo.tools.misc import file_open

from .common import TestItEdiStampPensionCommon

FLAT_RATE_XML = "IT00465840031_FLATR.xml"


def to_pay(*amounts):
    """XPath replacing the payment details with one instalment per amount."""
    details = "".join(
        "<DettaglioPagamento><ModalitaPagamento>MP05</ModalitaPagamento>"
        "<DataScadenzaPagamento>2026-12-02</DataScadenzaPagamento>"
        f"<ImportoPagamento>{amount}</ImportoPagamento></DettaglioPagamento>"
        for amount in amounts
    )
    return f'<xpath expr="//DettaglioPagamento" position="replace">{details}</xpath>'


@tagged("post_install_l10n", "post_install", "-at_install")
class TestStampDuty(TestItEdiStampPensionCommon):
    def _import(self, expected_values, xml_to_apply=None):
        return self._assert_import_invoice(FLAT_RATE_XML, [expected_values], xml_to_apply=xml_to_apply)

    def _stamp_lines(self, bill):
        return bill.invoice_line_ids.filtered(lambda line: line.product_id == self.stamp_product)

    def _set_stamp_product(self):
        self.company.l10n_it_edi_stamp_purchase_product_id = self.stamp_product

    def test_stamp_line_added_when_charged(self):
        self._set_stamp_product()
        bill = self._import({"amount_total": 126.8})
        self.assertRecordValues(self._stamp_lines(bill), [{
            "price_unit": 2.0,
            "tax_ids": self.tax_art15.ids,
            "account_id": self.company_data_2["default_account_expense"].id,
        }])

    def test_stamp_not_added_when_not_charged(self):
        self._set_stamp_product()
        bill = self._import({"amount_total": 124.8}, to_pay("124.80"))
        self.assertFalse(self._stamp_lines(bill))

    def test_stamp_not_added_when_already_a_line(self):
        self._set_stamp_product()
        bill = self._import({"amount_total": 126.8}, """
            <xpath expr="//DettaglioLinee" position="after">
                <DettaglioLinee>
                    <NumeroLinea>2</NumeroLinea>
                    <Descrizione>Imposta di bollo</Descrizione>
                    <Quantita>1.00</Quantita>
                    <PrezzoUnitario>2.000000</PrezzoUnitario>
                    <PrezzoTotale>2.00</PrezzoTotale>
                    <AliquotaIVA>0.00</AliquotaIVA>
                    <Natura>N1</Natura>
                </DettaglioLinee>
            </xpath>
            <xpath expr="//DatiRiepilogo" position="after">
                <DatiRiepilogo>
                    <AliquotaIVA>0.00</AliquotaIVA>
                    <Natura>N1</Natura>
                    <ImponibileImporto>2.00</ImponibileImporto>
                    <Imposta>0.00</Imposta>
                    <RiferimentoNormativo>Escluso art. 15</RiferimentoNormativo>
                </DatiRiepilogo>
            </xpath>
        """)
        self.assertEqual(len(bill.invoice_line_ids), 2)
        self.assertFalse(self._stamp_lines(bill))

    def test_stamp_not_added_on_rounding_difference(self):
        self._set_stamp_product()
        bill = self._import({"amount_total": 124.8}, to_pay("126.81"))
        self.assertFalse(self._stamp_lines(bill))

    def test_stamp_line_added_once(self):
        self._set_stamp_product()
        bill = self._import({"amount_total": 126.8})
        with file_open(f"{self.module}/tests/import_xmls/{FLAT_RATE_XML}", "rb") as xml_file:
            tree = etree.fromstring(xml_file.read())
        bill._l10n_it_edi_add_stamp_duty_line(tree)
        self.assertEqual(len(self._stamp_lines(bill)), 1)
        self.assertEqual(bill.amount_total, 126.8)

    def test_stamp_line_on_credit_note(self):
        self._set_stamp_product()
        bill = self._import(
            {"move_type": "in_refund", "amount_total": 126.8},
            '<xpath expr="//TipoDocumento" position="replace"><TipoDocumento>TD04</TipoDocumento></xpath>',
        )
        self.assertEqual(len(self._stamp_lines(bill)), 1)

    def test_stamp_line_with_installments(self):
        self._set_stamp_product()
        bill = self._import({"amount_total": 126.8}, to_pay("63.40", "63.40"))
        self.assertEqual(len(self._stamp_lines(bill)), 1)

    def test_stamp_without_product_logs_message(self):
        bill = self._import({"amount_total": 124.8})
        self.assertFalse(self._stamp_lines(bill))
        self.assertTrue(any("stamp duty product" in body for body in bill.message_ids.mapped("body")))

    def test_stamp_line_added_when_amount_omitted(self):
        # ImportoBollo is optional in the FatturaPA schema: BolloVirtuale SI alone
        # means the legal stamp duty of 2.00.
        self._set_stamp_product()
        bill = self._import({"amount_total": 126.8}, '<xpath expr="//ImportoBollo" position="replace"/>')
        self.assertRecordValues(self._stamp_lines(bill), [{"price_unit": 2.0}])

    def test_stamp_product_of_other_company(self):
        other_company_product = self.env["product.product"].create({
            "name": "Imposta di bollo (other company)",
            "type": "service",
            "company_id": self.company_data["company"].id,
        })
        self.company.l10n_it_edi_stamp_purchase_product_id = other_company_product
        bill = self._import({"amount_total": 124.8, "amount_untaxed": 120.0})
        self.assertNotIn(other_company_product, bill.invoice_line_ids.product_id)
        self.assertTrue(any("stamp duty product" in body for body in bill.message_ids.mapped("body")))
