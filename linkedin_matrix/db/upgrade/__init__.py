from mautrix.util.async_db import UpgradeTable

upgrade_table = UpgradeTable()

from . import v01_initial_revision  # noqa: E402

__all__ = ("v01_initial_revision",)
