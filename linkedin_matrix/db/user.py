from __future__ import annotations

from typing import cast

from asyncpg import Record
from attr import dataclass

from linkedin_messaging import URN
from mautrix.types import RoomID, UserID

from .model_base import Model


@dataclass
class User(Model):
    mxid: UserID
    li_member_urn: URN | None
    notice_room: RoomID | None
    space_mxid: RoomID | None

    _table_name = "user"
    _field_list = [
        "mxid",
        "li_member_urn",
        "notice_room",
        "space_mxid",
    ]

    @classmethod
    def _from_row(cls, row: Record | None) -> User | None:
        if row is None:
            return None
        data = {**row}
        li_member_urn = data.pop("li_member_urn")
        return cls(
            li_member_urn=URN(li_member_urn) if li_member_urn else None,
            **data,
        )

    @classmethod
    async def all_logged_in(cls) -> list["User"]:
        query = User.select_constructor("li_member_urn <> ''")
        rows = await cls.db.fetch(query)
        return [cast(User, cls._from_row(row)) for row in rows if row]

    @classmethod
    async def get_by_li_member_urn(cls, li_member_urn: URN) -> User | None:
        query = User.select_constructor("li_member_urn=$1")
        row = await cls.db.fetchrow(query, li_member_urn.id_str())
        return cls._from_row(row)

    @classmethod
    async def get_by_mxid(cls, mxid: UserID) -> User | None:
        query = User.select_constructor("mxid=$1")
        row = await cls.db.fetchrow(query, mxid)
        return cls._from_row(row)

    async def insert(self):
        query = User.insert_constructor()
        await self.db.execute(
            query,
            self.mxid,
            self.li_member_urn.id_str() if self.li_member_urn else None,
            self.notice_room,
            self.space_mxid,
        )

    async def delete(self):
        await self.db.execute('DELETE FROM "user" WHERE mxid=$1', self.mxid)

    async def save(self):
        query = """
            UPDATE "user"
               SET li_member_urn=$2,
                   notice_room=$3,
                   space_mxid=$4
             WHERE mxid=$1
        """
        await self.db.execute(
            query,
            self.mxid,
            self.li_member_urn.id_str() if self.li_member_urn else None,
            self.notice_room,
            self.space_mxid,
        )
