from __future__ import annotations

from typing import cast

from asyncpg import Record
from attr import dataclass
from linkedin_messaging import URN
from yarl import URL

from mautrix.types import ContentURI, SyncToken, UserID

from .model_base import Model


@dataclass
class Puppet(Model):
    li_member_urn: URN
    name: str | None
    photo_id: str | None
    photo_mxc: ContentURI | None

    custom_mxid: UserID | None
    access_token: str | None
    next_batch: SyncToken | None
    base_url: URL | None

    name_set: bool = False
    avatar_set: bool = False
    contact_info_set: bool = False
    is_registered: bool = False

    _table_name = "puppet"
    _field_list = [
        "li_member_urn",
        "name",
        "photo_id",
        "photo_mxc",
        "name_set",
        "avatar_set",
        "contact_info_set",
        "is_registered",
        "custom_mxid",
        "access_token",
        "next_batch",
        "base_url",
    ]

    @classmethod
    def _from_row(cls, row: Record | None) -> Puppet | None:
        if row is None:
            return None
        data = {**row}
        base_url = data.pop("base_url", None)
        li_member_urn = data.pop("li_member_urn")
        return cls(
            **data,
            base_url=URL(base_url) if base_url else None,
            li_member_urn=URN(li_member_urn),
        )

    @classmethod
    async def get_by_li_member_urn(cls, li_member_urn: URN) -> Puppet | None:
        query = Puppet.select_constructor("li_member_urn=$1")
        row = await cls.db.fetchrow(query, li_member_urn.id_str())
        return cls._from_row(row)

    @classmethod
    async def get_by_name(cls, name: str) -> Puppet | None:
        query = Puppet.select_constructor("name=$1")
        row = await cls.db.fetchrow(query, name)
        return cls._from_row(row)

    @classmethod
    async def get_by_custom_mxid(cls, mxid: UserID) -> Puppet | None:
        query = Puppet.select_constructor("custom_mxid=$1")
        row = await cls.db.fetchrow(query, mxid)
        return cls._from_row(row)

    @classmethod
    async def get_all_with_custom_mxid(cls) -> list["Puppet"]:
        query = Puppet.select_constructor("custom_mxid <> ''")
        rows = await cls.db.fetch(query)
        return [cast(Puppet, cls._from_row(row)) for row in rows if row]

    async def insert(self):
        query = Puppet.insert_constructor()
        await self.db.execute(
            query,
            self.li_member_urn.id_str(),
            self.name,
            self.photo_id,
            self.photo_mxc,
            self.name_set,
            self.avatar_set,
            self.contact_info_set,
            self.is_registered,
            self.custom_mxid,
            self.access_token,
            self.next_batch,
            str(self.base_url) if self.base_url else None,
        )

    async def delete(self):
        await self.db.execute(
            "DELETE FROM puppet WHERE li_member_urn=$1",
            self.li_member_urn.id_str(),
        )

    async def save(self):
        query = """
            UPDATE puppet
               SET name=$2,
                   photo_id=$3,
                   photo_mxc=$4,
                   name_set=$5,
                   avatar_set=$6,
                   contact_info_set=$7,
                   is_registered=$8,
                   custom_mxid=$9,
                   access_token=$10,
                   next_batch=$11,
                   base_url=$12
             WHERE li_member_urn=$1
        """
        await self.db.execute(
            query,
            self.li_member_urn.id_str(),
            self.name,
            self.photo_id,
            self.photo_mxc,
            self.name_set,
            self.avatar_set,
            self.contact_info_set,
            self.is_registered,
            self.custom_mxid,
            self.access_token,
            self.next_batch,
            str(self.base_url) if self.base_url else None,
        )
