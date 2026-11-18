from odoo.tests import tagged

from .common import TestItEdiStampPensionCommon


@tagged("post_install_l10n", "post_install", "-at_install")
class TestVatSearch(TestItEdiStampPensionCommon):
    def test_vat_4_not_pension_fund(self):
        self.tax_4_goods.active = True
        bill = self._assert_import_invoice(
            "IT00465840031_VAT4G.xml", [{"amount_untaxed": 10.0, "amount_tax": 0.4}]
        )
        self.assertEqual(bill.invoice_line_ids.tax_ids, self.tax_4_goods)

    def test_vat_4_archived_leaves_line_without_tax(self):
        # The standard chart archives the 4% purchase VAT: the line must stay
        # without tax instead of getting the active 4% INPS pension fund tax.
        bill = self._assert_import_invoice(
            "IT00465840031_VAT4G.xml", [{"amount_untaxed": 10.0, "amount_tax": 0.0}]
        )
        self.assertFalse(bill.invoice_line_ids.tax_ids)
