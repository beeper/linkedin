from mautrix.bridge import Bridge
from mautrix.types import UserID, RoomID

from .config import Config
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
