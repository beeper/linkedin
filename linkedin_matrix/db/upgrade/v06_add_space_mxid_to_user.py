from asyncpg import Connection

from . import upgrade_table


@upgrade_table.register(description="Add space MXID to User")
async def upgrade_v6(conn: Connection):
    create_table_queries = [
        """
        ALTER TABLE "user" ADD COLUMN space_mxid TEXT
        """,
    ]

    for query in create_table_queries:
        await conn.execute(query)
