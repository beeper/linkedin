import re
from html import escape
from typing import Any, Dict, List, Match, Optional, Union

from mautrix.types import Format, MessageType, TextMessageEventContent

from .. import puppet as pu, user as u

MENTION_REGEX = re.compile(r"@([0-9]{1,15})\u2063(.+?)\u2063")


async def linkedin_to_matrix(msg: Dict[str, Any]) -> TextMessageEventContent:
    text = msg.get("text", "")
    mentions = sorted(
        msg.get("attributes", []), key=lambda m: m.get("start"), reverse=True
    )

    content = TextMessageEventContent(msgtype=MessageType.TEXT, body=text)

    segments = []
    profile_urns = []
    for m in mentions:
        start, length = m.get("start"), m.get("length")
        profile_urn = (
            m.get("type", {})
            .get("com.linkedin.pemberly.text.Entity", {})
            .get("urn", "")
            .split(":")[-1]
        )
        if start is None or length is None or not profile_urn:
            continue

        text, original, after = (
            text[:start],
            text[start : start + length],
            text[start + length :],
        )
        segments.append(after)
        segments.append((original, profile_urn))
        profile_urns.append(profile_urn)

    segments.append(text)

    mention_user_map = {}
    for profile_urn in profile_urns:
        user = await u.User.get_by_li_member_urn(profile_urn)
        if user:
            mention_user_map[profile_urn] = user.mxid
        else:
            puppet = await pu.Puppet.get_by_li_member_urn(profile_urn, create=False)
            if puppet:
                mention_user_map[profile_urn] = puppet.mxid

    html = ""
    for segment in reversed(segments):
        if isinstance(segment, tuple):
            text, profile_urn = segment
            mxid = mention_user_map.get(profile_urn)
            if not text.startswith("@"):
                text = "@" + text

            if not mxid:
                html += text
            else:
                html += f'<a href="https://matrix.to/#/{mxid}">{text}</a>'
        else:
            html += escape(segment)

    html = html.replace("\n", "<br/>")

    if html != escape(content.body).replace("\n", "<br/>"):
        content.format = Format.HTML
        content.formatted_body = html

    return content
