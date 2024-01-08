from __future__ import annotations

from asyncpg import Record
from attr import dataclass

from mautrix.types import UserID

from .model_base import Model


@dataclass
class Cookie(Model):
    mxid: UserID
    name: str
    value: str

    _table_name = "cookie"
    _field_list = [
        "mxid",
        "name",
        "value",
    ]

    @classmethod
    def _from_row(cls, row: Record | None) -> Cookie | None:
        if row is None:
            return None
        return cls(**row)

    @classmethod
    async def get_for_mxid(cls, mxid: id.UserID) -> list[Cookie]:
        query = Cookie.select_constructor("mxid=$1")
        rows = await cls.db.fetch(query, mxid)
        return [cls._from_row(row) for row in rows if row]

    @classmethod
    async def delete_all_for_mxid(cls, mxid: id.UserID):
        await cls.db.execute("DELETE FROM cookie WHERE mxid=$1", mxid)

    @classmethod
    async def bulk_upsert(cls, mxid: id.UserID, cookies: dict[str, str]):
        for name, value in cookies.items():
            cookie = cls(mxid, name, value)
            await cookie.upsert()

    async def upsert(self):
        query = """
            INSERT INTO cookie (mxid, name, value)
                 VALUES ($1, $2, $3)
            ON CONFLICT (mxid, name)
                DO UPDATE
                    SET value=excluded.value
        """
        await self.db.execute(query, self.mxid, self.name, self.value)
