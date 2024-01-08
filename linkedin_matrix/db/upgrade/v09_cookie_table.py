from mautrix.util.async_db import Connection

from . import upgrade_table


@upgrade_table.register(description="Add a cookie table for storing all of the cookies")
async def upgrade_v9(conn: Connection):
    await conn.execute(
        """
        CREATE TABLE cookie (
            mxid  TEXT,
            name  TEXT,
            value TEXT,

            PRIMARY KEY (mxid, name)
        )
        """
    )

    for row in await conn.fetch('SELECT mxid, jsessionid, li_at FROM "user"'):
        mxid = row["mxid"]
        jsessionid = row["jsessionid"]
        li_at = row["li_at"]

        if jsessionid:
            await conn.execute(
                "INSERT INTO cookie (mxid, name, value) VALUES ($1, 'JSESSIONID', $2)",
                mxid,
                jsessionid,
            )
        if li_at:
            await conn.execute(
                "INSERT INTO cookie (mxid, name, value) VALUES ($1, 'li_at', $2)",
                mxid,
                li_at,
            )
