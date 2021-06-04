from typing import ClassVar, List, Optional, TYPE_CHECKING

from asyncpg import Record
from attr import dataclass
from mautrix.types import ContentURI, SyncToken, UserID
from mautrix.util.async_db import Database

from .model_base import Model

fake_db = Database("") if TYPE_CHECKING else None


@dataclass
class Puppet(Model):
    db: ClassVar[Database] = fake_db

    li_urn: str
    name: Optional[str]
    photo_id: Optional[str]
    photo_mxc: Optional[ContentURI]

    name_set: bool
    avatar_set: bool
    is_registered: bool

    custom_mxid: Optional[UserID]
    next_batch: Optional[SyncToken]

    _table_name = "puppet"
    _field_list = [
        "li_urn",
        "name",
        "photo_id",
        "photo_mxc",
        "name_set",
        "avatar_set",
        "is_registered",
        "custom_mxid",
        "next_batch",
    ]

    @classmethod
    def _from_row(cls, row: Optional[Record]) -> Optional["Puppet"]:
        if row is None:
            return None
        return cls(**row)

    @classmethod
    async def get_by_li_urn(cls, li_urn: str) -> Optional["Puppet"]:
        query = Puppet.select_constructor("li_urn=$1")
        row = await cls.db.fetchrow(query, li_urn)
        return cls._from_row(row)

    @classmethod
    async def get_by_name(cls, name: str) -> Optional["Puppet"]:
        query = Puppet.select_constructor("name=$1")
        row = await cls.db.fetchrow(query, name)
        return cls._from_row(row)

    @classmethod
    async def get_by_custom_mxid(cls, mxid: UserID) -> Optional["Puppet"]:
        query = Puppet.select_constructor("custom_mxid=$1")
        row = await cls.db.fetchrow(query, mxid)
        return cls._from_row(row)

    @classmethod
    async def get_all_with_custom_mxid(cls) -> List["Puppet"]:
        query = Puppet.select_constructor("custom_mxid <> ''")
        rows = await cls.db.fetch(query)
        return [cls._from_row(row) for row in rows]

    async def insert(self) -> None:
        query = Puppet.insert_constructor()
        await self.db.execute(
            query,
            self.li_urn,
            self.name,
            self.photo_id,
            self.photo_mxc,
            self.name_set,
            self.avatar_set,
            self.is_registered,
            self.custom_mxid,
            self.next_batch,
        )

    async def delete(self) -> None:
        await self.db.execute("DELETE FROM puppet WHERE li_urn=$1", self.li_urn)

    async def save(self) -> None:
        query = """
            UPDATE puppet
               SET name=$2,
                   photo_id=$3,
                   photo_mxc=$4,
                   name_set=$5,
                   avatar_set=$6,
                   is_registered=$7,
                   custom_mxid=$8,
                   next_batch=$9
             WHERE li_urn=$1
        """
        await self.db.execute(
            query,
            self.li_urn,
            self.name,
            self.photo_id,
            self.photo_mxc,
            self.name_set,
            self.avatar_set,
            self.is_registered,
            self.custom_mxid,
            self.next_batch,
        )
