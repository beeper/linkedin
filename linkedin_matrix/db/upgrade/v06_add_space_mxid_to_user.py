from mautrix.util.async_db import Connection

from . import upgrade_table


@upgrade_table.register(description="Add space MXID to User")
async def upgrade_v6(conn: Connection):
    await conn.execute('ALTER TABLE "user" ADD COLUMN space_mxid TEXT')
