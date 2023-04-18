from mautrix.util.async_db import Connection

from . import upgrade_table


@upgrade_table.register(description="Add contact_info_set column to puppet table")
async def upgrade_v7(conn: Connection):
    await conn.execute(
        "ALTER TABLE puppet ADD COLUMN contact_info_set BOOLEAN NOT NULL DEFAULT false"
    )
