from __future__ import annotations

from typing import cast

from asyncpg import Record
from attr import dataclass
from linkedin_messaging import URN

from mautrix.types import ContentURI, RoomID

from .model_base import Model


@dataclass
class Portal(Model):
    li_thread_urn: URN
    li_receiver_urn: URN | None
    li_is_group_chat: bool
    li_other_user_urn: URN | None

    mxid: RoomID | None
    encrypted: bool

    name: str | None
    photo_id: str | None
    avatar_url: ContentURI | None
    topic: str | None
    name_set: bool
    avatar_set: bool
    topic_set: bool

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
        "topic",
        "name_set",
        "avatar_set",
        "topic_set",
    ]

    @classmethod
    def _from_row(cls, row: Record | None) -> Portal | None:
        if row is None:
            return None
        data = {**row}
        li_thread_urn = data.pop("li_thread_urn")
        li_receiver_urn = data.pop("li_receiver_urn", None)
        li_other_user_urn = data.pop("li_other_user_urn", None)
        return cls(
            **data,
            li_thread_urn=URN(li_thread_urn),
            li_receiver_urn=URN(li_receiver_urn) if li_receiver_urn else None,
            li_other_user_urn=URN(li_other_user_urn) if li_other_user_urn else None,
        )

    @classmethod
    async def get_by_li_thread_urn(
        cls,
        li_thread_urn: URN,
        li_receiver_urn: URN | None,
    ) -> Portal | None:
        query = Portal.select_constructor("li_thread_urn=$1 AND li_receiver_urn=$2")
        row = await cls.db.fetchrow(
            query,
            li_thread_urn.id_str(),
            li_receiver_urn.id_str() if li_receiver_urn else None,
        )
        return cls._from_row(row)

    @classmethod
    async def get_by_mxid(cls, mxid: RoomID) -> Portal | None:
        query = Portal.select_constructor("mxid=$1")
        row = await cls.db.fetchrow(query, mxid)
        return cls._from_row(row)

    @classmethod
    async def get_all_by_li_receiver_urn(cls, li_receiver_urn: URN) -> list["Portal"]:
        query = Portal.select_constructor("li_receiver_urn=$1")
        rows = await cls.db.fetch(query, li_receiver_urn.id_str())
        return [cast(Portal, cls._from_row(row)) for row in rows if row]

    @classmethod
    async def all(cls) -> list["Portal"]:
        query = Portal.select_constructor()
        rows = await cls.db.fetch(query)
        return [cast(Portal, cls._from_row(row)) for row in rows if row]

    async def insert(self):
        query = Portal.insert_constructor()
        await self.db.execute(
            query,
            self.li_thread_urn.id_str(),
            self.li_receiver_urn.id_str() if self.li_receiver_urn else None,
            self.li_is_group_chat,
            self.li_other_user_urn.id_str() if self.li_other_user_urn else None,
            self.mxid,
            self.encrypted,
            self.name,
            self.photo_id,
            self.avatar_url,
            self.topic,
            self.name_set,
            self.avatar_set,
            self.topic_set,
        )

    async def delete(self):
        q = "DELETE FROM portal WHERE li_thread_urn=$1 AND li_receiver_urn=$2"
        await self.db.execute(
            q,
            self.li_thread_urn.id_str(),
            self.li_receiver_urn.id_str() if self.li_receiver_urn else None,
        )

    async def save(self):
        query = """
            UPDATE portal
               SET li_is_group_chat=$3,
                   li_other_user_urn=$4,
                   mxid=$5,
                   encrypted=$6,
                   name=$7,
                   photo_id=$8,
                   avatar_url=$9,
                   topic=$10,
                   name_set=$11,
                   avatar_set=$12,
                   topic_set=$13
             WHERE li_thread_urn=$1
               AND li_receiver_urn=$2
        """
        await self.db.execute(
            query,
            self.li_thread_urn.id_str(),
            self.li_receiver_urn.id_str() if self.li_receiver_urn else None,
            self.li_is_group_chat,
            self.li_other_user_urn.id_str() if self.li_other_user_urn else None,
            self.mxid,
            self.encrypted,
            self.name,
            self.photo_id,
            self.avatar_url,
            self.topic,
            self.name_set,
            self.avatar_set,
            self.topic_set,
        )
