from mautrix.util.async_db import UpgradeTable

upgrade_table = UpgradeTable()

from . import (  # noqa: E402
    v01_initial_revision,
    v02_multiple_reaction_per_message,
    v03_add_topic_to_portal,
    v04_add_portal_meta_set,
    v05_add_index_to_reaction,
    v06_add_space_mxid_to_user,
    v07_puppet_contact_info_set,
    v08_splat_pickle_data,
    v09_cookie_table,
    v10_http_header_table,
)

__all__ = (
    "v01_initial_revision",
    "v02_multiple_reaction_per_message",
    "v03_add_topic_to_portal",
    "v04_add_portal_meta_set",
    "v05_add_index_to_reaction",
    "v06_add_space_mxid_to_user",
    "v07_puppet_contact_info_set",
    "v08_splat_pickle_data",
    "v09_cookie_table",
    "v10_http_header_table",
)
