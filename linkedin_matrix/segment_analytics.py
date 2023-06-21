from __future__ import annotations

import logging

from yarl import URL
import aiohttp

from mautrix.util import background_task

from . import user as u

log = logging.getLogger("mau.web.public.analytics")
segment_url: URL = URL("https://api.segment.io/v1/track")
http: aiohttp.ClientSession | None = None
segment_key: str | None = None
segment_user_id: str | None = None


async def _track(user: u.User, event: str, properties: dict) -> None:
    assert segment_key
    assert http
    await http.post(
        segment_url,
        json={
            "userId": segment_user_id or user.mxid,
            "event": event,
            "properties": {"bridge": "linkedin", **properties},
        },
        auth=aiohttp.BasicAuth(login=segment_key, encoding="utf-8"),
    )
    log.debug(f"Tracked {event}")


def track(user: u.User, event: str, properties: dict | None = None):
    if segment_key:
        background_task.create(_track(user, event, properties or {}))


def init(key: str | None, user_id: str | None = None):
    if not key:
        return
    log.info("Initialising Segment.io analytics")
    global segment_key, segment_user_id, http
    segment_key = key
    segment_user_id = user_id
    http = aiohttp.ClientSession()
