# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from .common import WithholdingCommon


class TestTaxBasePercent(WithholdingCommon):
    def test_core_templates(self):
        ref = self.env["account.chart.template"].with_company(self.company).ref
        self.assertEqual(ref("23awo").l10n_it_wt_base_percent, 50.0)
        self.assertEqual(ref("23awn").l10n_it_wt_base_percent, 20.0)
        self.assertEqual(self.wt_purchase.l10n_it_wt_base_percent, 100.0)

    def test_custom_tax_11_5(self):
        tax = self.env["account.tax"].create(
            {
                "name": "Ritenuta 11.5%",
                "amount": -11.5,
                "type_tax_use": "purchase",
                "l10n_it_withholding_type": "RT02",
                "l10n_it_withholding_reason": "ZO",
                "company_id": self.company.id,
            }
        )
        self.assertEqual(tax.l10n_it_wt_base_percent, 50.0)

    def test_manual_override_kept(self):
        self.wt_purchase.l10n_it_wt_base_percent = 78.0
        self.wt_purchase.name = "renamed"
        self.assertEqual(self.wt_purchase.l10n_it_wt_base_percent, 78.0)
