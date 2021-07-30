from typing import Optional

from mautrix.bridge import Bridge
from mautrix.bridge.state_store.asyncpg import PgBridgeStateStore
from mautrix.types import RoomID, UserID
from mautrix.util.async_db import Database
from mautrix.util.bridge_state import BridgeState, BridgeStateEvent

from . import commands  # noqa: F401
from .config import Config
from .db import init as init_db, upgrade_table
from .puppet import Puppet
from .portal import Portal  # noqa: I100 (needs to be after because it relies on Puppet)
from .user import User
from .version import linkified_version, version
from .web import ProvisioningAPI

# This has to be imported after the rest of the modules because it relies on them
# being imported already.
from .matrix import MatrixHandler  # noqa: I100 I202


class LinkedInBridge(Bridge):
    name = "linkedin-matrix"
    module = "linkedin_matrix"
    command = "linkedin-matrix"
    description = "A Matrix-LinkedIn Messages puppeting bridge."
    repo_url = "https://github.com/sumnerevans/linkedin-matrix"
    real_user_content_key = "com.sumnerevans.linkedin.puppet"
    version = version
    markdown_version = linkified_version
    config_class = Config
    matrix_class = MatrixHandler

    config: Config
    db: Database
    matrix: MatrixHandler
    provisioning_api: ProvisioningAPI
    state_store: PgBridgeStateStore

    def make_state_store(self):
        self.state_store = PgBridgeStateStore(
            self.db,
            self.get_puppet,
            self.get_double_puppet,
        )

    def prepare_db(self):
        self.db = Database(
            self.config["appservice.database"],
            upgrade_table=upgrade_table,
            loop=self.loop,
            db_args=self.config["appservice.database_opts"],
        )
        init_db(self.db)

    def prepare_stop(self):
        # self.periodic_reconnect_task.cancel()
        self.log.debug("Stopping puppet syncers")
        for puppet in Puppet.by_custom_mxid.values():
            puppet.stop()
        self.log.debug("Stopping LinkedIn listeners")
        User.shutdown = True
        for user in User.by_li_member_urn.values():
            user.stop_listen()

    def prepare_bridge(self):
        super().prepare_bridge()
        cfg = self.config["appservice.provisioning"]
        self.provisioning_api = ProvisioningAPI(cfg["shared_secret"])
        self.az.app.add_subapp(cfg["prefix"], self.provisioning_api.app)

    async def stop(self):
        await super().stop()
        await Puppet.close()
        self.log.debug("Saving user sessions")
        for user in User.by_mxid.values():
            await user.save()

    async def start(self):
        await self.db.start()
        await self.state_store.upgrade_table.upgrade(self.db.pool)
        if self.matrix.e2ee and self.matrix.e2ee.crypto_db:
            self.matrix.e2ee.crypto_db.override_pool(self.db.pool)

        # Let the API server know that we are alive.
        state = BridgeState(state_event=BridgeStateEvent.UNCONFIGURED)
        await state.send(
            self.config["homeserver.status_endpoint"], self.az.as_token, self.log
        )

        self.add_startup_actions(User.init_cls(self))
        self.add_startup_actions(Puppet.init_cls(self))
        Portal.init_cls(self)
        if self.config["bridge.resend_bridge_info"]:
            self.add_startup_actions(self.resend_bridge_info())
        await super().start()

    async def resend_bridge_info(self):
        self.config["bridge.resend_bridge_info"] = False
        self.config.save()
        self.log.info("Re-sending bridge info state event to all portals")
        async for portal in Portal.all():
            await portal.update_bridge_info()
        self.log.info("Finished re-sending bridge info state events")

    async def get_portal(self, room_id: RoomID) -> Portal:
        return await Portal.get_by_mxid(room_id)

    async def get_puppet(
        self, user_id: UserID, create: bool = False
    ) -> Optional[Puppet]:
        return await Puppet.get_by_mxid(user_id, create=create)

    async def get_double_puppet(self, user_id: UserID) -> Puppet:
        return await Puppet.get_by_custom_mxid(user_id)

    async def get_user(self, user_id: UserID, create: bool = True) -> User:
        return await User.get_by_mxid(user_id, create=create)

    def is_bridge_ghost(self, user_id: UserID) -> bool:
        return bool(Puppet.get_id_from_mxid(user_id))


def main():
    LinkedInBridge().run()


if __name__ == "__main__":
    main()
