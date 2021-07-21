from mautrix.util.async_db import Database

from .message import Message
from .portal import Portal
from .puppet import Puppet
from .reaction import Reaction
from .upgrade import upgrade_table
from .user import User
from .user_portal import UserPortal


def init(db: Database):
    for table in (Message, Portal, Puppet, Reaction, User, UserPortal):
        table.db = db  # type: ignore


__all__ = (
    "init",
    "upgrade_table",
    # Models
    "Message",
    "Model",
    "Portal",
    "Puppet",
    "Reaction",
    "User",
    "UserPortal",
)
