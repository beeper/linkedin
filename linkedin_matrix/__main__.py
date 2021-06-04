from typing import Optional

from mautrix.bridge import Bridge
from mautrix.bridge.state_store.asyncpg import PgBridgeStateStore
from mautrix.types import UserID, RoomID
from mautrix.util.async_db import Database

from .config import Config
from .db import upgrade_table, init as init_db
from .matrix import MatrixHandler
from .portal import Portal
from .puppet import Puppet
from .user import User
from .version import version, linkified_version


class LinkedInBridge(Bridge):
    name = "linkedin-matrix"
    module = "linkedin_matrix"
    command = "linkedin-matrix"
    description = "A Matrix-LinkedIn Messages puppeting bridge."
    repo_url = "https://github.com/sumnerevans/linkedin-matrix"
    real_user_content_key = "com.github.sumnerevans.linkedinmatrix.puppet"
    version = version
    markdown_version = linkified_version
    config_class = Config
    matrix_class = MatrixHandler

    db: Database
    config: Config
    matrix: MatrixHandler
    # public_website: Optional[PublicBridgeWebsite]
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

    async def start(self):
        await self.db.start()
        await self.state_store.upgrade_table.upgrade(self.db.pool)
        if self.matrix.e2ee:
            self.matrix.e2ee.crypto_db.override_pool(self.db.pool)
        self.add_startup_actions(User.init_cls(self))
        self.add_startup_actions(Puppet.init_cls(self))
        Portal.init_cls(self)
        # if self.config["bridge.resend_bridge_info"]:
        #     self.add_startup_actions(self.resend_bridge_info())
        await super().start()
        # if self.public_website:
        #     self.public_website.ready_wait.set_result(None)
        # self.periodic_reconnect_task = asyncio.create_task(self._try_periodic_reconnect_loop())

    async def get_portal(self, room_id: RoomID) -> Portal:
        return await Portal.get_by_mxid(room_id)

    async def get_puppet(self, user_id: UserID, create: bool = False) -> Puppet:
        return await Puppet.get_by_mxid(user_id, create=create)

    async def get_double_puppet(self, user_id: UserID) -> Puppet:
        return await Puppet.get_by_custom_mxid(user_id)

    async def get_user(self, user_id: UserID, create: bool = True) -> User:
        print("get_user", user_id, create)
        return await User.get_by_mxid(user_id, create=create)

    def is_bridge_ghost(self, user_id: UserID) -> bool:
        print("is_bridge_ghost", user_id)
        return bool(Puppet.get_id_from_mxid(user_id))


def main():
    LinkedInBridge().run()


if __name__ == "__main__":
    main()
