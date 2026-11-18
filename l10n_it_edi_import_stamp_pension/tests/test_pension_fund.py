from odoo.tests import tagged

from .common import TestItEdiStampPensionCommon


@tagged("post_install_l10n", "post_install", "-at_install")
class TestPensionFund(TestItEdiStampPensionCommon):
    def test_pension_fund_on_flat_rate_line(self):
        bill = self._assert_import_invoice(
            "IT00465840031_FLATR.xml",
            [{"amount_untaxed": 120.0, "amount_tax": 4.8, "amount_total": 124.8}],
        )
        self.assertEqual(bill.invoice_line_ids.tax_ids, self.tax_n22 | self.tax_inps)
