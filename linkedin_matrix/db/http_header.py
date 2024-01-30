from __future__ import annotations

from asyncpg import Record
from attr import dataclass

from mautrix.types import UserID

from .model_base import Model


@dataclass
class HttpHeader(Model):
    mxid: UserID
    name: str
    value: str

    _table_name = "http_header"
    _field_list = [
        "mxid",
        "name",
        "value",
    ]

    @classmethod
    def _from_row(cls, row: Record | None) -> HttpHeader | None:
        if row is None:
            return None
        return cls(**row)

    @classmethod
    async def get_for_mxid(cls, mxid: id.UserID) -> list[HttpHeader]:
        query = HttpHeader.select_constructor("mxid=$1")
        rows = await cls.db.fetch(query, mxid)
        return [cls._from_row(row) for row in rows if row]

    @classmethod
    async def delete_all_for_mxid(cls, mxid: id.UserID):
        await cls.db.execute("DELETE FROM http_header WHERE mxid=$1", mxid)

    @classmethod
    async def bulk_upsert(cls, mxid: id.UserID, http_headers: dict[str, str]):
        for name, value in http_headers.items():
            http_header = cls(mxid, name, value)
            await http_header.upsert()

    async def upsert(self):
        query = """
            INSERT INTO http_header (mxid, name, value)
                 VALUES ($1, $2, $3)
            ON CONFLICT (mxid, name)
                DO UPDATE
                    SET value=excluded.value
        """
        await self.db.execute(query, self.mxid, self.name, self.value)
