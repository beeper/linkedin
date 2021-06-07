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
    li_message_urn: Optional[str]
    li_thread_urn: str
    li_sender_urn: str
    li_receiver_urn: str
    index: int
    timestamp: int

    _table_name = "message"
    _field_list = [
        "mxid",
        "mx_room",
        "li_message_urn",
        "li_thread_urn",
        "li_sender_urn",
        "li_receiver_urn",
        "index",
        "timestamp",
    ]

    @classmethod
    def _from_row(cls, row: Optional[Record]) -> Optional["Message"]:
        if row is None:
            return None
        return cls(**row)

    @classmethod
    async def get_all_by_li_message_urn(
        cls,
        li_message_urn: str,
        li_receiver_urn: str,
    ) -> List["Message"]:
        query = Message.select_constructor("li_message_urn=$1 AND li_receiver_urn=$2")
        rows = await cls.db.fetch(query, li_message_urn, li_receiver_urn)
        return [cls._from_row(row) for row in rows]

    @classmethod
    async def delete_all_by_room(cls, room_id: RoomID) -> None:
        await cls.db.execute("DELETE FROM message WHERE mx_room=$1", room_id)

    @classmethod
    async def get_by_mxid(cls, mxid: EventID, mx_room: RoomID) -> Optional["Message"]:
        query = Message.select_constructor("mxid=$1 AND mx_room=$2")
        row = await cls.db.fetchrow(query, mxid, mx_room)
        return cls._from_row(row)

    async def insert(self) -> None:
        query = Message.insert_constructor()
        await self.db.execute(
            query,
            self.mxid,
            self.mx_room,
            self.li_message_urn,
            self.li_thread_urn,
            self.li_sender_urn,
            self.li_receiver_urn,
            self.index,
            self.timestamp,
        )

    async def delete(self) -> None:
        q = """
            DELETE FROM message
             WHERE li_message_urn=$1
               AND li_receiver_urn=$2
               AND index=$3"
        """
        await self.db.execute(q, self.li_message_urn, self.li_receiver_urn, self.index)
