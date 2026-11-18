# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from .common import WithholdingCommon


class TestSetup(WithholdingCommon):
    def test_core_withholding_is_cash_basis(self):
        self.assertEqual(self.wt_purchase.tax_exigibility, "on_payment")
        self.assertTrue(self.company.tax_exigibility)
        self.assertTrue(self.company.tax_cash_basis_journal_id)
        self.assertEqual(self.wt_payable.code, "260200")
