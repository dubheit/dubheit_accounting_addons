# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# Copyright 2026 Dubhe Srls
{
    "name": "Italian Localization - E-bill Import: Pension Fund and Stamp Duty",
    "summary": "Pension fund on 0% lines, stamp duty line and cleaner VAT search when importing vendor e-bills",
    "description": """
Improves the import of Italian vendor e-bills (FatturaPA XML):

* applies the pension fund (DatiCassaPrevidenziale) also to 0% VAT lines with
  a Natura code, as flat-rate suppliers send them (backport of the fix in the
  newer Odoo 19 builds; it does nothing where the core already applies it);
* adds the stamp duty as a bill line when the supplier charges it, that is when
  the amount to pay in the XML exceeds the bill total by exactly the stamp duty;
* never picks a pension fund or withholding tax as the VAT of a line.

Configuration: set the stamp duty product (expense account and purchase tax,
usually 0% excluded art. 15) in Settings > Italian Electronic Invoicing.
    """,
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations",
    "author": "Dubhe Srls",
    "website": "https://github.com/dubheit/dubheit_accounting_addons",
    "license": "AGPL-3",
    "depends": [
        "l10n_it_edi",
    ],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
}
