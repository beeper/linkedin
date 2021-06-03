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
    name = "mautrix-linkedin"
    module = "mautrix_linkedin"
    command = "mautrix-linkedin"
    description = "A Matrix-LinkedIn Messages puppeting bridge."
    version = version
    markdown_version = linkified_version
    config_class = Config
    matrix_class = MatrixHandler

    db: Database
    config: Config
    state_store: PgBridgeStateStore

    def make_state_store(self) -> None:
        self.state_store = PgBridgeStateStore(
            self.db,
            self.get_puppet,
            self.get_double_puppet,
        )

    def prepare_db(self) -> None:
        self.db = Database(
            self.config["appservice.database"],
            upgrade_table=upgrade_table,
            loop=self.loop,
            db_args=self.config["appservice.database_opts"],
        )
        init_db(self.db)

    async def start(self) -> None:
        await self.db.start()
        await self.state_store.upgrade_table.upgrade(self.db.pool)
        if self.matrix.e2ee:
            self.matrix.e2ee.crypto_db.override_pool(self.db.pool)

    async def get_user(self, user_id: UserID, create: bool = True) -> User:
        raise NotImplementedError()

    async def get_portal(self, room_id: RoomID) -> Portal:
        raise NotImplementedError()

    async def get_puppet(self, user_id: UserID, create: bool = False) -> Puppet:
        raise NotImplementedError()

    async def get_double_puppet(self, user_id: UserID) -> Puppet:
        raise NotImplementedError()

    def is_bridge_ghost(self, user_id: UserID) -> bool:
        raise NotImplementedError()


def main():
    LinkedInBridge().run()


if __name__ == "__main__":
    main()
