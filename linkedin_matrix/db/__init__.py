from mautrix.util.async_db import Database

from .cookie import Cookie
from .http_header import HttpHeader
from .message import Message
from .model_base import Model
from .portal import Portal
from .puppet import Puppet
from .reaction import Reaction
from .upgrade import upgrade_table
from .user import User
from .user_portal import UserPortal


def init(db: Database):
    for table in (HttpHeader, Cookie, Message, Portal, Puppet, Reaction, User, UserPortal):
        table.db = db  # type: ignore


__all__ = (
    "init",
    "upgrade_table",
    # Models
    "HttpHeader",
    "Cookie",
    "Message",
    "Model",
    "Portal",
    "Puppet",
    "Reaction",
    "User",
    "UserPortal",
)
