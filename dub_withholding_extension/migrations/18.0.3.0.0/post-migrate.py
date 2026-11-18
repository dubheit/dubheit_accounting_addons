# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Upgrade from 18.0.2.0.0.

    Payment types: payable accounts recomputed from the taxes and made
    reconcilable. Register filters: dropped, the fields of the view changed.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    types = env["withholding.payment.type"].with_context(active_test=False).search([])
    types._l10n_it_wt_refresh_accounts()
    filters = (
        env["ir.filters"]
        .with_context(active_test=False)
        .search([("model_id", "=", "l10n_it.withholding.tax.report")])
    )
    _logger.info(
        "Withholding upgrade: %s payment types refreshed, %s register filters "
        "removed",
        len(types),
        len(filters),
    )
    filters.unlink()
