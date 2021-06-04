from mautrix.util.async_db import Database

from .upgrade import upgrade_table
from .user import User


def init(db: Database) -> None:
    for table in (User,):
        table.db = db


__all__ = (
    "init",
    "upgrade_table",
    "User",
)
