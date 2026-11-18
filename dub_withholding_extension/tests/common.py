# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class WithholdingCommon(AccountTestInvoicingCommon):
    @classmethod
    @AccountTestInvoicingCommon.setup_country("it")
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        template = cls.env["account.chart.template"].with_company(cls.company)
        cls.wt_purchase = template.ref("20awi")
        cls.wt_sale = template.ref("20vwi")
        cls.wt_23_purchase = template.ref("23awo")
        cls.wt_payable = template.ref("2602")
        cls.vat_purchase = cls.company.account_purchase_tax_id
        cls.vat_sale = cls.company.account_sale_tax_id

    @classmethod
    def _wt_invoice(cls, move_type, amount, taxes, date, partner=None, post=True):
        return cls._create_invoice_one_line(
            move_type=move_type,
            partner_id=partner or cls.partner_a,
            price_unit=amount,
            tax_ids=taxes,
            invoice_date=date,
            date=date,
            post=post,
        )

    @classmethod
    def _wt_pay(cls, move, amount, date):
        return cls._register_payment(move, amount=amount, payment_date=date)

    def _register_rows(self, invoice):
        self.env.flush_all()
        return self.env["l10n_it.withholding.tax.report"].search(
            [("invoice_id", "=", invoice.id)], order="payment_date, id"
        )
