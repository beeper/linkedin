import json
from typing import ClassVar, List, Optional, TYPE_CHECKING

from asyncpg import Record
from attr import dataclass
from mautrix.types import RoomID, UserID
from mautrix.util.async_db import Database
from requests.cookies import cookiejar_from_dict, RequestsCookieJar

from .model_base import Model

fake_db = Database("") if TYPE_CHECKING else None


@dataclass
class User(Model):
    db: ClassVar[Database] = fake_db

    mxid: UserID
    li_member_urn: Optional[str]
    notice_room: Optional[RoomID]

    cookies: Optional[RequestsCookieJar]

    _table_name = "user"
    _field_list = ["mxid", "li_member_urn", "cookies", "notice_room"]

    @property
    def _cookies_json(self) -> Optional[str]:
        return json.dumps(dict(self.cookies)) if self.cookies else None

    @classmethod
    def _from_row(cls, row: Optional[Record]) -> Optional["User"]:
        if row is None:
            return None
        data = {**row}
        cookies = data.pop("cookies", None)
        user = cls(**data)
        if cookies is not None:
            user.cookies = cookiejar_from_dict(json.loads(cookies))
        return user

    @classmethod
    async def all_logged_in(cls) -> List["User"]:
        query = User.select_constructor("li_member_urn <> ''")
        rows = await cls.db.fetch(query)
        return [cls._from_row(row) for row in rows]

    @classmethod
    async def get_by_li_member_urn(cls, li_member_urn: str) -> Optional["User"]:
        query = User.select_constructor("li_member_urn=$1")
        row = await cls.db.fetchrow(query, li_member_urn)
        return cls._from_row(row)

    @classmethod
    async def get_by_mxid(cls, mxid: UserID) -> Optional["User"]:
        query = User.select_constructor("mxid=$1")
        row = await cls.db.fetchrow(query, mxid)
        return cls._from_row(row)

    async def insert(self):
        query = User.insert_constructor()
        await self.db.execute(
            query,
            self.mxid,
            self.li_member_urn,
            self._cookies_json,
            self.notice_room,
        )

    async def delete(self):
        await self.db.execute('DELETE FROM "user" WHERE mxid=$1', self.mxid)

    async def save(self) -> None:
        query = """
            UPDATE "user"
               SET li_member_urn=$2,
                   cookies=$3,
                   notice_room=$4
             WHERE mxid=$1
        """
        await self.db.execute(
            query,
            self.mxid,
            self.li_member_urn,
            self._cookies_json,
            self.notice_room,
        )
