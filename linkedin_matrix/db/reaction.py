from typing import ClassVar, List, Optional, TYPE_CHECKING

from asyncpg import Record
from attr import dataclass
from mautrix.types import EventID, RoomID
from mautrix.util.async_db import Database

from .model_base import Model

fake_db = Database("") if TYPE_CHECKING else None


@dataclass
class Reaction(Model):
    db: ClassVar[Database] = fake_db

    mxid: EventID
    mx_room: RoomID
    li_msg_urn: str
    li_receiver: int
    li_sender: int
    reaction: str

    @classmethod
    def _from_row(cls, row: Optional[Record]) -> Optional["Reaction"]:
        if row is None:
            return None
        return cls(**row)

    async def insert(self):
        query = Reaction.insert_constructor()
        await self.db.execute(
            query,
            self.mxid,
            self.mx_room,
            self.li_msg_urn,
            self.li_receiver,
            self.li_sender,
            self.reaction,
        )

    async def delete(self):
        query = """
            DELETE FROM reaction
             WHERE li_msg_urn=$1
               AND li_receiver=$2
               AND li_sender=$3
        """
        await self.db.execute(query, self.li_msg_urn, self.li_receiver, self.li_sender)

    async def save(self):
        query = """
            UPDATE reaction
               SET mxid=$1,
                   mx_room=$2,
                   reaction=$3
             WHERE li_msg_urn=$1
               AND li_receiver=$2
               AND li_sender=$3
        """
        await self.db.execute(
            query,
            self.mxid,
            self.mx_room,
            self.reaction,
            self.li_msg_urn,
            self.li_receiver,
            self.li_sender,
        )
