import logging
import pickle

from mautrix.util.async_db import Connection

from . import upgrade_table


@upgrade_table.register(
    description="Add credential columns to user table and populate them from client_pickle"
)
async def upgrade_v8(conn: Connection):
    # First, add the columns for JSESSIONID and li_at.
    await conn.execute('ALTER TABLE "user" ADD COLUMN jsessionid TEXT')
    await conn.execute('ALTER TABLE "user" ADD COLUMN li_at TEXT')

    # Now, unpickle the data from client_pickle and put it into the new columns.
    for row in await conn.fetch('SELECT mxid, client_pickle FROM "user"'):
        user_id = row["mxid"]
        client_pickle = row["client_pickle"]
        if client_pickle is None:
            logging.warning(f"User {user_id} has no client_pickle")
            continue

        cookies = pickle.loads(client_pickle)
        jsessionid, li_at = None, None
        for cookies in cookies.values():
            if j := cookies.get("JSESSIONID"):
                jsessionid = j.value
            if li := cookies.get("li_at"):
                li_at = li.value

        if not jsessionid or not li_at:
            logging.warning(f"User {user_id} doesn't have JSESSIONID or li_at")
            continue

        await conn.execute(
            'UPDATE "user" SET jsessionid = $1, li_at = $2 WHERE mxid = $3',
            jsessionid,
            li_at,
            user_id,
        )
