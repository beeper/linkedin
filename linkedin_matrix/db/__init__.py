from mautrix.util.async_db import Database

from .message import Message
from .portal import Portal
from .puppet import Puppet
from .upgrade import upgrade_table
from .user import User


def init(db: Database) -> None:
    for table in (User, Puppet):
        table.db = db


__all__ = (
    "init",
    "upgrade_table",
    # Models
    "Message",
    "Model",
    "Portal",
    "Puppet",
    "User",
)
