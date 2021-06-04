from typing import ClassVar, List, Optional, TYPE_CHECKING

from asyncpg import Record
from attr import dataclass
from mautrix.types import ContentURI, RoomID
from mautrix.util.async_db import Database

from .model_base import Model

fake_db = Database("") if TYPE_CHECKING else None


@dataclass
class Portal(Model):
    db: ClassVar[Database] = fake_db

    li_urn: str
    li_receiver: str
    mxid: Optional[RoomID]
    name: Optional[str]
    photo_id: Optional[str]
    avatar_url: Optional[ContentURI]
    encrypted: bool

    _table_name = "portal"
    _field_list = [
        "li_urn",
        "li_receiver",
        "mxid",
        "name",
        "photo_id",
        "avatar_url",
        "encrypted",
    ]

    @classmethod
    def _from_row(cls, row: Optional[Record]) -> Optional["Portal"]:
        if row is None:
            return None
        return cls(**row)

    @classmethod
    async def get_by_li_urn(cls, li_urn: str, li_receiver: str) -> Optional["Portal"]:
        query = Portal.select_constructor("li_urn=$1 AND li_receiver=$2")
        row = await cls.db.fetchrow(query, li_urn, li_receiver)
        return cls._from_row(row)

    @classmethod
    async def get_by_mxid(cls, mxid: RoomID) -> Optional["Portal"]:
        query = Portal.select_constructor("mxid=$1")
        row = await cls.db.fetchrow(query, mxid)
        return cls._from_row(row)

    @classmethod
    async def get_all_by_receiver(cls, li_receiver: str) -> List["Portal"]:
        query = Portal.select_constructor("li_receiver=$1")
        rows = await cls.db.fetch(query, li_receiver)
        return [cls._from_row(row) for row in rows]

    @classmethod
    async def all(cls) -> List["Portal"]:
        query = Portal.select_constructor()
        rows = await cls.db.fetch(query)
        return [cls._from_row(row) for row in rows]

    async def insert(self):
        query = Portal.insert_constructor()
        await self.db.execute(
            query,
            self.li_urn,
            self.li_receiver,
            self.mxid,
            self.name,
            self.photo_id,
            self.avatar_url,
            self.encrypted,
        )

    async def delete(self):
        q = "DELETE FROM portal WHERE li_urn=$1 AND li_receiver=$2"
        await self.db.execute(q, self.li_urn, self.li_receiver)

    async def save(self):
        query = """
            UPDATE portal
               SET mxid=$3,
                   name=$4,
                   photo_id=$5,
                   avatar_url=$6,
                   encrypted=$7
             WHERE li_urn=$1
               AND li_receiver=$2
        """
        await self.db.execute(
            query,
            self.li_urn,
            self.li_receiver,
            self.mxid,
            self.name,
            self.photo_id,
            self.avatar_url,
            self.encrypted,
        )
