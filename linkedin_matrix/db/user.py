from typing import Optional, List, TYPE_CHECKING, ClassVar

from asyncpg import Record
from attr import dataclass

from mautrix.types import UserID, RoomID
from mautrix.util.async_db import Database

fake_db = Database("") if TYPE_CHECKING else None


@dataclass
class User:
    db: ClassVar[Database] = fake_db

    mxid: UserID
    linkedin_urn: Optional[str]

    @classmethod
    def _from_row(cls, row: Optional[Record]) -> Optional["User"]:
        if row is None:
            return None
        return cls(**row)

    @classmethod
    async def all_logged_in(cls) -> List["User"]:
        rows = await cls.db.fetch(
            """
            SELECT mxid, linkedin_urn
            FROM "user"
            WHERE fbid<>""
            """
        )
        return [cls._from_row(row) for row in rows]
