from typing import Optional

from asyncpg import Record
from attr import dataclass

from .model_base import Model


@dataclass
class UserPortal(Model):
    user: str
    portal: str
    portal_receiver: str

    _table_name = "user_portal"
    _field_list = ["user", "portal", "portal_receiver"]

    @classmethod
    def _from_row(cls, row: Optional[Record]) -> Optional["UserPortal"]:
        if row is None:
            return None
        return cls(**row)

    @classmethod
    async def all(cls, user: str) -> dict[str, "UserPortal"]:
        query = UserPortal.select_constructor('"user"=$1')
        rows = await cls.db.fetch(query, user)
        return {up.portal: up for up in (cls._from_row(row) for row in rows) if up}

    @classmethod
    async def get(
        cls,
        user: str,
        portal: str,
        portal_receiver: str,
    ) -> Optional["UserPortal"]:
        query = UserPortal.select_constructor(
            '"user"=$1 AND portal=$2 AND portal_receiver=$3'
        )
        row = await cls.db.fetchrow(query, user, portal, portal_receiver)
        return cls._from_row(row)

    async def insert(self):
        query = UserPortal.insert_constructor()
        await self.db.execute(query, self.user, self.portal, self.portal_receiver)

    async def delete(self):
        query = """
            DELETE FROM user_portal
             WHERE "user"=$1
               AND portal=$2
               AND portal_receiver=$3
        """
        await self.db.execute(query, self.user, self.portal, self.portal_receiver)

    @classmethod
    async def delete_all(cls, user: int):
        await cls.db.execute('DELETE FROM user_portal WHERE "user"=$1', user)
