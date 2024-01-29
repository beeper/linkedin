from mautrix.util.async_db import Connection

from . import upgrade_table


@upgrade_table.register(description="Add a header table for storing all of the headers")
async def upgrade_v10(conn: Connection):
    await conn.execute(
        """
        CREATE TABLE http_header (
            mxid  TEXT,
            name  TEXT,
            value TEXT,

            PRIMARY KEY (mxid, name)
        )
        """
    )
