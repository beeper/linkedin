from mautrix.util.async_db import Database

from .upgrade import upgrade_table

def init(db: Database) -> None:
    pass


__all__ = ("upgrade_table", "init")
