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

    @classmethod
    def _wt_pay_after_lock(cls, move, payment_date, lock_date):
        """Pay ``move`` on ``payment_date``, lock the period, then match them.

        The cash basis entry cannot go in the locked period, so it is dated
        after ``lock_date`` while the payment stays before it.
        """
        payment = cls.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": move.partner_id.id,
                "amount": move.amount_total,
                "date": payment_date,
                "journal_id": cls.company_data["default_journal_bank"].id,
            }
        )
        payment.action_post()
        cls.company.fiscalyear_lock_date = lock_date
        account = move.line_ids.filtered(
            lambda line: line.display_type == "payment_term"
        ).account_id
        (move.line_ids | payment.move_id.line_ids).filtered(
            lambda line: line.account_id == account
        ).reconcile()
        return payment

    def _register_rows(self, invoice):
        # SQL view: flush the changes and drop the rows already in cache
        self.env.flush_all()
        self.env.invalidate_all()
        return self.env["l10n_it.withholding.tax.report"].search(
            [("invoice_id", "=", invoice.id)], order="payment_date, id"
        )
