from asyncpg import Connection

from . import upgrade_table


@upgrade_table.register(
    description="Multiple reactions per message",
    transaction=False,
)
async def upgrade_v1(conn: Connection):
    create_table_queries = [
        """
        ALTER TABLE reaction DROP CONSTRAINT reaction_pkey
        """,
        """
        ALTER TABLE reaction ADD PRIMARY KEY (
            li_message_urn,
            li_receiver_urn,
            li_sender_urn,
            reaction
        )
        """,
    ]

    for query in create_table_queries:
        await conn.execute(query)
