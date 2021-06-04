from typing import Any, Tuple, List
import os

from mautrix.bridge.config import BaseBridgeConfig
from mautrix.types import UserID
from mautrix.util.config import ConfigUpdateHelper, ForbiddenDefault, ForbiddenKey


class Config(BaseBridgeConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        super().do_update(helper)
        copy, copy_dict, base = helper
        copy_dict("bridge.permissions")

    def _get_permissions(self, key: str) -> Tuple[bool, bool, str]:
        level = self["bridge.permissions"].get(key, "")
        admin = level == "admin"
        user = level == "user" or admin
        return user, admin, level

    def get_permissions(self, mxid: UserID) -> Tuple[bool, bool, str]:
        permissions = self["bridge.permissions"] or {}
        if mxid in permissions:
            return self._get_permissions(mxid)

        homeserver = mxid[mxid.index(":") + 1 :]
        if homeserver in permissions:
            return self._get_permissions(homeserver)

        return self._get_permissions("*")
