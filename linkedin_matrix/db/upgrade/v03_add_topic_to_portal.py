from asyncpg import Connection

from . import upgrade_table


@upgrade_table.register(description="Add topic to portals")
async def upgrade_v1(conn: Connection):
    create_table_queries = [
        """
        ALTER TABLE portal ADD COLUMN topic TEXT
        """,
    ]

    for query in create_table_queries:
        await conn.execute(query)
