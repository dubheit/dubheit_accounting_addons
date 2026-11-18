# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    result = env["withholding.history.statement"]._import_from_oca()
    _logger.info(
        "OCA withholding history imported: %(statements)s statements, "
        "%(moves)s moves",
        result,
    )
