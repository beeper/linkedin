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

    li_thread_urn: str
    li_receiver_urn: Optional[str]
    li_is_group_chat: bool
    li_other_user_urn: Optional[str]

    mxid: Optional[RoomID]
    encrypted: bool

    name: Optional[str]
    photo_id: Optional[str]
    avatar_url: Optional[ContentURI]

    _table_name = "portal"
    _field_list = [
        # LinkedIn chat information
        "li_thread_urn",
        "li_receiver_urn",
        "li_is_group_chat",
        "li_other_user_urn",
        # Matrix portal information
        "mxid",
        "encrypted",
        # Chat metadata
        "name",
        "photo_id",
        "avatar_url",
    ]

    @classmethod
    def _from_row(cls, row: Optional[Record]) -> Optional["Portal"]:
        if row is None:
            return None
        return cls(**row)

    @classmethod
    async def get_by_li_thread_urn(
        cls,
        li_thread_urn: str,
        li_receiver_urn: str,
    ) -> Optional["Portal"]:
        query = Portal.select_constructor("li_thread_urn=$1 AND li_receiver_urn=$2")
        row = await cls.db.fetchrow(query, li_thread_urn, li_receiver_urn)
        return cls._from_row(row)

    @classmethod
    async def get_by_mxid(cls, mxid: RoomID) -> Optional["Portal"]:
        query = Portal.select_constructor("mxid=$1")
        row = await cls.db.fetchrow(query, mxid)
        return cls._from_row(row)

    @classmethod
    async def get_all_by_receiver(cls, li_receiver_urn: str) -> List["Portal"]:
        query = Portal.select_constructor("li_receiver_urn=$1")
        rows = await cls.db.fetch(query, li_receiver_urn)
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
            self.li_thread_urn,
            self.li_receiver_urn,
            self.li_is_group_chat,
            self.li_other_user_urn,
            self.mxid,
            self.encrypted,
            self.name,
            self.photo_id,
            self.avatar_url,
        )

    async def delete(self):
        q = "DELETE FROM portal WHERE li_thread_urn=$1 AND li_receiver_urn=$2"
        await self.db.execute(q, self.li_thread_urn, self.li_receiver_urn)

    async def save(self):
        query = """
            UPDATE portal
               SET li_is_group_chat=$3,
                   li_other_user_urn=$4,
                   mxid=$5,
                   encrypted=$6,
                   name=$7,
                   photo_id=$8,
                   avatar_url=$9
             WHERE li_thread_urn=$1
               AND li_receiver_urn=$2
        """
        await self.db.execute(
            query,
            self.li_thread_urn,
            self.li_receiver_urn,
            self.li_is_group_chat,
            self.li_other_user_urn,
            self.mxid,
            self.encrypted,
            self.name,
            self.photo_id,
            self.avatar_url,
        )
