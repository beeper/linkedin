from typing import Optional

from asyncpg import Record
from attr import dataclass
from linkedin_messaging import URN
from mautrix.types import EventID, RoomID

from .model_base import Model


@dataclass
class Reaction(Model):
    mxid: EventID
    mx_room: RoomID
    li_message_urn: URN
    li_receiver_urn: URN
    li_sender_urn: URN
    reaction: str

    _table_name = "reaction"
    _field_list = [
        "mxid",
        "mx_room",
        "li_message_urn",
        "li_receiver_urn",
        "li_sender_urn",
        "reaction",
    ]

    @classmethod
    def _from_row(cls, row: Optional[Record]) -> Optional["Reaction"]:
        if row is None:
            return None
        data = {**row}
        li_message_urn = data.pop("li_message_urn")
        li_receiver_urn = data.pop("li_receiver_urn")
        li_sender_urn = data.pop("li_sender_urn")
        return cls(
            **data,
            li_message_urn=URN(li_message_urn),
            li_receiver_urn=URN(li_receiver_urn),
            li_sender_urn=URN(li_sender_urn),
        )

    @classmethod
    async def get_by_mxid(cls, mxid: EventID, mx_room: RoomID) -> Optional["Reaction"]:
        query = Reaction.select_constructor("mxid=$1 AND mx_room=$2")
        row = await cls.db.fetchrow(query, mxid, mx_room)
        return cls._from_row(row)

    @classmethod
    async def get_by_li_message_urn_and_emoji(
        cls,
        li_message_urn: URN,
        li_receiver_urn: URN,
        li_sender_urn: URN,
        reaction: str,
    ) -> Optional["Reaction"]:
        query = Reaction.select_constructor(
            """
                li_message_urn=$1
            AND li_receiver_urn=$2
            AND li_sender_urn=$3
            AND reaction=$4
            """
        )
        row = await cls.db.fetchrow(
            query,
            li_message_urn.id_str(),
            li_receiver_urn.id_str(),
            li_sender_urn.id_str(),
            reaction,
        )
        return cls._from_row(row)

    async def insert(self):
        query = Reaction.insert_constructor()
        await self.db.execute(
            query,
            self.mxid,
            self.mx_room,
            self.li_message_urn.id_str(),
            self.li_receiver_urn.id_str(),
            self.li_sender_urn.id_str(),
            self.reaction,
        )

    async def delete(self):
        query = """
            DELETE FROM reaction
             WHERE li_message_urn=$1
               AND li_receiver_urn=$2
               AND li_sender_urn=$3
        """
        await self.db.execute(
            query,
            self.li_message_urn.id_str(),
            self.li_receiver_urn.id_str(),
            self.li_sender_urn.id_str(),
        )

    async def save(self):
        query = """
            UPDATE reaction
               SET mxid=$1,
                   mx_room=$2,
                   reaction=$3
             WHERE li_message_urn=$1
               AND li_receiver_urn=$2
               AND li_sender_urn=$3
        """
        await self.db.execute(
            query,
            self.mxid,
            self.mx_room,
            self.reaction,
            self.li_message_urn.id_str(),
            self.li_receiver_urn.id_str(),
            self.li_sender_urn.id_str(),
        )
