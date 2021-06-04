from typing import Optional, List, TYPE_CHECKING, ClassVar

from asyncpg import Record
from attr import dataclass
from yarl import URL

from mautrix.types import UserID, SyncToken, ContentURI
from mautrix.util.async_db import Database

fake_db = Database("") if TYPE_CHECKING else None


@dataclass
class Puppet:
    db: ClassVar[Database] = fake_db

    linkedin_urn: str

    @classmethod
    def _from_row(cls, row: Optional[Record]) -> Optional['Puppet']:
        if row is None:
            return None
        data = {**row}
        return cls(**data)

    @classmethod
    async def get_all_with_custom_mxid(cls) -> List['Puppet']:
        q = """
            SELECT linkedin_urn
            FROM puppet
            WHERE custom_mxid<>''
        """
        rows = await cls.db.fetch(q)
        return [cls._from_row(row) for row in rows]
