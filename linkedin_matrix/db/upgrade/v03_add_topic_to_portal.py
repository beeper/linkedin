from mautrix.util.async_db import Connection

from . import upgrade_table


@upgrade_table.register(description="Add topic to portals")
async def upgrade_v3(conn: Connection):
    await conn.execute("ALTER TABLE portal ADD COLUMN topic TEXT")
