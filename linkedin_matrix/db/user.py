from typing import ClassVar, List, Optional, TYPE_CHECKING

from asyncpg import Record
from attr import dataclass
from mautrix.types import RoomID, UserID
from mautrix.util.async_db import Database

from .model_base import Model

fake_db = Database("") if TYPE_CHECKING else None


@dataclass
class User(Model):
    db: ClassVar[Database] = fake_db

    mxid: UserID
    li_urn: Optional[str]
    notice_room: Optional[RoomID]

    _table_name = "user"
    _field_list = ["mxid", "li_urn", "notice_room"]

    @classmethod
    def _from_row(cls, row: Optional[Record]) -> Optional["User"]:
        if row is None:
            return None
        return cls(**row)

    @classmethod
    async def all_logged_in(cls) -> List["User"]:
        query = User.select_constructor("li_urn <> ''")
        rows = await cls.db.fetch(query)
        return [cls._from_row(row) for row in rows]

    @classmethod
    async def get_by_li_urn(cls, li_urn: str) -> Optional["User"]:
        query = User.select_constructor("li_urn=$1")
        row = await cls.db.fetchrow(query, li_urn)
        return cls._from_row(row)

    @classmethod
    async def get_by_mxid(cls, mxid: UserID) -> Optional["User"]:
        query = User.select_constructor("mxid=$1")
        row = await cls.db.fetchrow(query, mxid)
        return cls._from_row(row)

    async def insert(self):
        query = User.insert_constructor()
        print(query)
        await self.db.execute(query, self.mxid, self.li_urn, self.notice_room)

    async def delete(self):
        await self.db.execute('DELETE FROM "user" WHERE mxid=$1', self.mxid)

    async def save(self) -> None:
        query = """
            UPDATE "user"
               SET li_urn=$2,
                   notice_room=$3
             WHERE mxid=$1
        """
        await self.db.execute(query, self.mxid, self.li_urn, self.notice_room)
