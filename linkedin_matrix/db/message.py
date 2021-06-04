from typing import ClassVar, List, Optional, TYPE_CHECKING

from asyncpg import Record
from attr import dataclass
from mautrix.types import EventID, RoomID
from mautrix.util.async_db import Database

from .model_base import Model

fake_db = Database("") if TYPE_CHECKING else None


@dataclass
class Message(Model):
    db: ClassVar[Database] = fake_db

    mxid: EventID
    mx_room: RoomID
    li_urn: Optional[str]
    li_message_urn: Optional[str]
    index: int
    li_chat_urn: str
    li_receiver: str
    li_sender: str
    timestamp: int

    _table_name = "message"
    _field_list = [
        "mxid",
        "mx_room",
        "li_urn",
        "li_message_urn",
        "index",
        "li_chat_urn",
        "li_receiver",
        "li_sender",
        "timestamp",
    ]

    @classmethod
    def _from_row(cls, row: Optional[Record]) -> Optional["Message"]:
        if row is None:
            return None
        return cls(**row)

    @classmethod
    async def get_all_by_li_urn(cls, li_urn: str, li_receiver: str) -> List["Message"]:
        query = Message.select_constructor("li_urn=$1 AND li_receiver=$2")
        rows = await cls.db.fetch(query, li_urn, li_receiver)
        return [cls._from_row(row) for row in rows]

    @classmethod
    async def get_by_li_urn(
        cls,
        li_urn: str,
        li_receiver: str,
        index: int = 0,
    ) -> Optional["Message"]:
        query = Message.select_constructor("li_urn=$1 AND li_receiver=$2 AND index=$3")
        row = await cls.db.fetchrow(query, li_urn, li_receiver, index)
        return cls._from_row(row)

    @classmethod
    async def delete_all_by_room(cls, room_id: RoomID) -> None:
        await cls.db.execute("DELETE FROM message WHERE mx_room=$1", room_id)

    @classmethod
    async def get_by_mxid(cls, mxid: EventID, mx_room: RoomID) -> Optional["Message"]:
        query = Message.select_constructor("mxid=$1 AND mx_room=$2")
        row = await cls.db.fetchrow(query, mxid, mx_room)
        return cls._from_row(row)

    @classmethod
    async def get_most_recent(
        cls,
        li_chat_urn: int,
        li_receiver: int,
    ) -> Optional["Message"]:
        query = (
            Message.select_constructor(
                "li_chat_urn=$1 AND li_receiver=$2 AND li_urn IS NOT NULL"
            )
            + " ORDER BY timestamp DESC LIMIT 1"
        )
        row = await cls.db.fetchrow(query, li_chat_urn, li_receiver)
        return cls._from_row(row)

    @classmethod
    async def get_closest_before(
        cls,
        li_chat_urn: int,
        li_receiver: int,
        timestamp: int,
    ) -> Optional["Message"]:
        query = (
            Message.select_constructor(
                """
                    li_chat_urn=$1
                AND li_receiver=$2
                AND timestamp<=$3
                AND li_urn IS NOT NULL
                """
            )
            + " ORDER BY timestamp DESC LIMIT 1"
        )
        row = await cls.db.fetchrow(query, li_chat_urn, li_receiver, timestamp)
        return cls._from_row(row)

    async def insert(self) -> None:
        query = Message.insert_constructor()
        await self.db.execute(
            query,
            self.mxid,
            self.mx_room,
            self.li_urn,
            self.li_message_urn,
            self.index,
            self.li_chat_urn,
            self.li_receiver,
            self.li_sender,
            self.timestamp,
        )

    async def delete(self) -> None:
        q = "DELETE FROM message WHERE li_urn=$1 AND li_receiver=$2 AND index=$3"
        await self.db.execute(q, self.li_urn, self.li_receiver, self.index)

    async def update(self) -> None:
        query = """
            UPDATE message
               SET li_urn=$1,
                   timestamp=$2
             WHERE mxid=$3
               AND mx_room=$4
        """
        await self.db.execute(
            query,
            self.li_urn,
            self.timestamp,
            self.mxid,
            self.mx_room,
        )
