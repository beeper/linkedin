from __future__ import annotations

from typing import cast
from datetime import datetime

from asyncpg import Record
from attr import dataclass
from linkedin_messaging import URN

from mautrix.types import EventID, RoomID
from mautrix.util.async_db import Scheme

from .model_base import Model


@dataclass
class Message(Model):
    mxid: EventID
    mx_room: RoomID
    li_message_urn: URN
    li_thread_urn: URN
    li_sender_urn: URN
    li_receiver_urn: URN
    index: int
    timestamp: datetime

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
    def _from_row(cls, row: Record | None) -> Message | None:
        if row is None:
            return None
        data = {**row}
        li_message_urn = data.pop("li_message_urn")
        li_thread_urn = data.pop("li_thread_urn")
        li_sender_urn = data.pop("li_sender_urn")
        li_receiver_urn = data.pop("li_receiver_urn")
        timestamp = data.pop("timestamp")
        return cls(
            **data,
            li_message_urn=URN(li_message_urn),
            li_thread_urn=URN(li_thread_urn),
            li_sender_urn=URN(li_sender_urn),
            li_receiver_urn=URN(li_receiver_urn),
            timestamp=datetime.fromtimestamp(timestamp),
        )

    @classmethod
    async def get_all_by_li_message_urn(
        cls,
        li_message_urn: URN,
        li_receiver_urn: URN,
    ) -> list["Message"]:
        query = Message.select_constructor("li_message_urn=$1 AND li_receiver_urn=$2")
        rows = await cls.db.fetch(query, li_message_urn.id_str(), li_receiver_urn.id_str())
        return [cast(Message, cls._from_row(row)) for row in rows if row]

    @classmethod
    async def get_by_li_message_urn(
        cls,
        li_message_urn: URN,
        li_receiver_urn: URN,
        index: int = 0,
    ) -> Message | None:
        query = Message.select_constructor(
            """
            li_message_urn=$1 AND li_receiver_urn=$2 AND "index"=$3'
            """
        )
        row = await cls.db.fetchrow(
            query,
            li_message_urn.id_str(),
            li_receiver_urn.id_str(),
            index,
        )
        return cls._from_row(row)

    @classmethod
    async def delete_all_by_room(cls, room_id: RoomID):
        await cls.db.execute("DELETE FROM message WHERE mx_room=$1", room_id)

    @classmethod
    async def get_by_mxid(cls, mxid: EventID, mx_room: RoomID) -> Message | None:
        query = Message.select_constructor("mxid=$1 AND mx_room=$2")
        row = await cls.db.fetchrow(query, mxid, mx_room)
        return cls._from_row(row)

    @classmethod
    async def get_most_recent(
        cls,
        li_thread_urn: URN,
        li_receiver_urn: URN,
    ) -> Message | None:
        query = (
            Message.select_constructor("li_thread_urn=$1 AND li_receiver_urn=$2")
            + ' ORDER BY timestamp DESC, "index" DESC'
            + " LIMIT 1"
        )
        row = await cls.db.fetchrow(query, li_thread_urn.id_str(), li_receiver_urn.id_str())
        return cls._from_row(row)

    async def insert(self):
        query = Message.insert_constructor()
        await self.db.execute(
            query,
            self.mxid,
            self.mx_room,
            self.li_message_urn.id_str(),
            self.li_thread_urn.id_str(),
            self.li_sender_urn.id_str(),
            self.li_receiver_urn.id_str(),
            self.index,
            self.timestamp.timestamp(),
        )

    @classmethod
    async def bulk_create(
        cls,
        li_message_urn: URN,
        li_thread_urn: URN,
        li_sender_urn: URN,
        li_receiver_urn: URN,
        timestamp: datetime,
        event_ids: list[EventID],
        mx_room: RoomID,
    ):
        if not event_ids:
            return

        records = [
            (
                mxid,
                mx_room,
                li_message_urn.id_str(),
                li_thread_urn.id_str(),
                li_sender_urn.id_str(),
                li_receiver_urn.id_str(),
                index,
                timestamp.timestamp(),
            )
            for index, mxid in enumerate(event_ids)
        ]
        async with cls.db.acquire() as conn, conn.transaction():
            if cls.db.scheme == Scheme.POSTGRES:
                await conn.copy_records_to_table(
                    "message", records=records, columns=cls._field_list
                )
            else:
                await conn.executemany(Message.insert_constructor(), records)

    async def delete(self):
        q = """
            DELETE FROM message
             WHERE li_message_urn=$1
               AND li_receiver_urn=$2
               AND "index"=$3
        """
        await self.db.execute(
            q,
            self.li_message_urn.id_str(),
            self.li_receiver_urn.id_str(),
            self.index,
        )
