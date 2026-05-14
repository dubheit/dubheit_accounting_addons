{
    "name": "DUB 3-Way Match for SDI Bills",
    "version": "18.0.1.0.0",
    "category": "Accounting/Accounting",
    "summary": "Auto-link Italian SDI vendor bills to purchase orders for 3-way matching",
    "description": """
DUB 3-Way Match for SDI Bills
=============================

When a vendor bill is imported from SDI (FatturaPA XML), this module tries to
automatically link each invoice line to the corresponding purchase order line
so that Odoo's native 3-way matching (release_to_pay) can work.

Matching strategy:

1. Standard ``l10n_it_edi`` already resolves ``product_id`` on invoice lines
   from the XML ``<CodiceArticolo>`` node, using either the EAN (barcode) or
   the supplier code on ``product.supplierinfo``.
2. This module adds the missing step: for each invoice line with a resolved
   product, it searches for an open purchase order line of the same vendor
   and product with residual quantity to invoice. If exactly one candidate is
   found, ``purchase_line_id`` is set on the invoice line.
3. Ambiguous cases (multiple candidates) are left untouched so that the user
   can resolve them manually via the standard "Purchase Matching" view.

Depends on the Enterprise module ``account_3way_match`` to expose the
``release_to_pay`` status on linked bills.
    """,
    "author": "Dubhe Srls",
    "website": "https://www.dubhe.it",
    "license": "LGPL-3",
    "depends": [
        "l10n_it_edi",
        "purchase_stock",
        "account_3way_match",
    ],
    "data": [],
    "installable": True,
    "auto_install": False,
}
