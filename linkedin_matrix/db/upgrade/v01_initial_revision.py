from asyncpg import Connection

from . import upgrade_table


@upgrade_table.register(description="Initial asyncpg revision", transaction=False)
async def upgrade_v1(conn: Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE "user" (
            mxid            TEXT PRIMARY KEY,
            linkedin_urn    TEXT UNIQUE
        )
        """
    )
