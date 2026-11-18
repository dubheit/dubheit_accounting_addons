from odoo import Command
from odoo.tests import tagged

from odoo.addons.l10n_it_edi.tests.common import TestItEdi


@tagged("post_install_l10n", "post_install", "-at_install")
class TestItEdiStampPensionCommon(TestItEdi):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.module = "l10n_it_edi_import_stamp_pension"

        def ref(xmlid):
            return cls.env["account.chart.template"].with_company(cls.company).ref(xmlid)

        cls.tax_inps = ref("4ainps")
        cls.tax_4_goods = ref("4am")
        cls.tax_art15 = ref("00art15a")
        cls.tax_n22 = ref("00as").copy(
            {
                "name": "0% N2.2",
                "l10n_it_exempt_reason": "N2.2",
                "tax_scope": False,
                "invoice_legal_notes": "Regime forfettario",
            }
        )
        cls.stamp_product = (
            cls.env["product.product"]
            .with_company(cls.company)
            .create(
                {
                    "name": "Imposta di bollo",
                    "type": "service",
                    "supplier_taxes_id": [Command.set(cls.tax_art15.ids)],
                    "property_account_expense_id": cls.company_data_2["default_account_expense"].id,
                }
            )
        )
