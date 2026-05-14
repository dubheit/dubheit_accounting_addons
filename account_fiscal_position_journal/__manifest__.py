# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# Copyright 2025 Openindustry.it - Andrea M. Piovesana

{
    "name": "Account Fiscal Position Default Journal",
    "summary": "Default sales/purchase journals per fiscal position",
    "version": "18.0.1.1.0",
    "category": "Accounting/Accounting",
    "author": "Openindustry.it, Dubhe Srls",
    "website": "https://github.com/OCA/account-invoicing",
    "license": "AGPL-3",
    "depends": [
        "account",
        "sale",
        "purchase",
    ],
    "data": [
        "views/fiscal_position_view.xml",
    ],
    "installable": True,
}
