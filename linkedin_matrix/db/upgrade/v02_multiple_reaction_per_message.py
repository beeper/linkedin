from mautrix.util.async_db import Connection, Scheme

from . import upgrade_table


@upgrade_table.register(description="Multiple reactions per message")
async def upgrade_v2(conn: Connection, scheme: Scheme):
    if scheme != Scheme.SQLITE:
        await conn.execute("ALTER TABLE reaction DROP CONSTRAINT reaction_pkey")
        await conn.execute(
            """
            ALTER TABLE reaction ADD PRIMARY KEY (
                li_message_urn,
                li_receiver_urn,
                li_sender_urn,
                reaction
            )
            """
        )
    else:
        await conn.execute(
            """
            CREATE TABLE reaction_v2 (
                mxid            TEXT,
                mx_room         TEXT,
                li_message_urn  TEXT,
                li_receiver_urn TEXT,
                li_sender_urn   TEXT,
                reaction        TEXT,

                PRIMARY KEY (li_message_urn, li_receiver_urn, li_sender_urn, reaction),

                UNIQUE (mxid, mx_room)
            )
            """
        )
        await conn.execute(
            """
            INSERT INTO reaction_v2 (mxid, mx_room, li_message_urn, li_receiver_urn, reaction)
            SELECT mxid, mx_room, li_message_urn, li_receiver_urn, reaction FROM reaction
            """
        )
        await conn.execute("DROP TABLE reaction")
        await conn.execute("ALTER TABLE reaction_v2 RENAME TO reaction")
