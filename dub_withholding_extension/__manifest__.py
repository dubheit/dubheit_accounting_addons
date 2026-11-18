# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# Copyright 2026 Dubhe Srls

{
    "name": "Italian Localization - Withholding Tax Extension",
    "summary": "Withholding register, F24 payments, CU summary and OCA history on top of native taxes",
    "version": "18.0.3.0.0",
    "category": "Accounting/Localizations",
    "author": "Dubhe Srls",
    "website": "https://github.com/dubheit/dubheit_accounting_addons",
    "license": "AGPL-3",
    "depends": [
        "account",
        "l10n_it_edi_withholding",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "views/account_tax_views.xml",
        "views/res_config_settings_views.xml",
        "views/withholding_payment_type_views.xml",
        "views/withholding_payment_views.xml",
        "views/withholding_due_lines_views.xml",
        "views/withholding_invoice_report_views.xml",
        "wizard/withholding_payment_create_views.xml",
        "views/withholding_history_views.xml",
        "views/menu_views.xml",
    ],
    "installable": True,
}
