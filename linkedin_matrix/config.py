import os
from typing import Any

from mautrix.bridge.config import BaseBridgeConfig
from mautrix.types import UserID
from mautrix.util.config import ConfigUpdateHelper, ForbiddenDefault, ForbiddenKey


class Config(BaseBridgeConfig):
    def __getitem__(self, key: str) -> Any:
        try:
            return os.environ[f"MAUTRIX_LINKEDIN_{key.replace('.', '_').upper()}"]
        except KeyError:
            return super().__getitem__(key)

    @property
    def forbidden_defaults(self) -> list[ForbiddenDefault]:
        return [
            *super().forbidden_defaults,
            ForbiddenDefault(
                "appservice.database", "postgres://username:password@hostname/db"
            ),
            ForbiddenDefault("bridge.permissions", ForbiddenKey("example.com")),
        ]

    def do_update(self, helper: ConfigUpdateHelper):
        super().do_update(helper)
        copy, copy_dict, base = helper.copy, helper.copy_dict, helper.base

        copy("homeserver.asmux")

        # appservice
        copy("appservice.bot_avatar")
        copy("appservice.provisioning.enabled")
        copy("appservice.provisioning.prefix")
        copy("appservice.provisioning.shared_secret")
        if base["appservice.provisioning.shared_secret"] == "generate":
            base["appservice.provisioning.shared_secret"] = self._new_token()

        # bridge
        copy("bridge.backfill.disable_notifications")
        copy("bridge.backfill.initial_limit")
        copy("bridge.backfill.invite_own_puppet")
        copy("bridge.backfill.missed_limit")
        copy("bridge.command_prefix")
        copy("bridge.delivery_receipts")
        copy("bridge.displayname_preference")
        copy("bridge.displayname_template")
        copy("bridge.double_puppet_allow_discovery")
        copy("bridge.double_puppet_server_map")
        copy("bridge.encryption.allow")
        copy("bridge.encryption.default")
        copy("bridge.encryption.key_sharing.allow")
        copy("bridge.encryption.key_sharing.require_cross_signing")
        copy("bridge.encryption.key_sharing.require_verification")
        copy("bridge.initial_chat_sync")
        copy("bridge.invite_own_puppet_to_pm")
        copy("bridge.mute_bridging")
        copy("bridge.resend_bridge_info")
        copy("bridge.set_topic_on_dms")
        copy("bridge.sync_direct_chat_list")
        copy("bridge.sync_with_custom_puppets")
        copy("bridge.tag_only_on_create")
        copy("bridge.temporary_disconnect_notices")
        copy("bridge.username_template")

        if "bridge.login_shared_secret" in self:
            base["bridge.login_shared_secret_map"] = {
                base["homeserver.domain"]: self["bridge.login_shared_secret"]
            }
        else:
            copy("bridge.login_shared_secret_map")

        copy_dict("bridge.permissions")

        # Metrics
        copy("metrics.enabled")
        copy("metrics.listen_port")

    def _get_permissions(self, key: str) -> tuple[bool, bool, str]:
        level = self["bridge.permissions"].get(key, "")
        admin = level == "admin"
        user = level == "user" or admin
        return user, admin, level

    def get_permissions(self, mxid: UserID) -> tuple[bool, bool, str]:
        permissions = self["bridge.permissions"] or {}
        if mxid in permissions:
            return self._get_permissions(mxid)

        homeserver = mxid[mxid.index(":") + 1 :]
        if homeserver in permissions:
            return self._get_permissions(homeserver)

        return self._get_permissions("*")
