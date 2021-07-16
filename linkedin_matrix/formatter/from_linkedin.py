from html import escape
from typing import Union

from bs4 import BeautifulSoup
from linkedin_messaging import URN
from linkedin_messaging.api_objects import AttributedBody, SpInmailContent
from mautrix.types import Format, MessageType, TextMessageEventContent

from .. import puppet as pu, user as u


def linkedin_subject_to_matrix(subject: str) -> TextMessageEventContent:
    body = f"Subject: {subject}"
    return TextMessageEventContent(
        msgtype=MessageType.TEXT,
        body=body,
        format=Format.HTML,
        formatted_body=f"<b>{body}</b>",
    )


async def linkedin_to_matrix(msg: AttributedBody) -> TextMessageEventContent:
    content = TextMessageEventContent(msgtype=MessageType.TEXT, body=msg.text)

    segments: list[Union[str, tuple[str, URN]]] = []
    profile_urns = []

    text = msg.text
    for m in sorted(msg.attributes, key=lambda a: a.start, reverse=True):
        if (
            m.start is None
            or m.length is None
            or not m.type_
            or not m.type_.text_entity
            or not m.type_.text_entity.urn
        ):
            continue

        text, original, after = (
            text[: m.start],
            text[m.start : m.start + m.length],
            text[m.start + m.length :],
        )
        segments.append(after)
        segments.append((original, m.type_.text_entity.urn))
        profile_urns.append(m.type_.text_entity.urn)

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


async def linkedin_spinmail_to_matrix(
    sp_inmail_content: SpInmailContent,
) -> TextMessageEventContent:
    label, body = sp_inmail_content.advertiser_label, sp_inmail_content.body
    html_message = f"""<i>{label}</i>{body}"""
    if sp_inmail_content.sub_content and sp_inmail_content.sub_content.standard:
        action, action_text = (
            sp_inmail_content.sub_content.standard.action,
            sp_inmail_content.sub_content.standard.action_text,
        )
        html_message += f'<p><a href="{action}"><b>{action_text}</b></a></p>'

    if sp_inmail_content.legal_text:
        html_message += sp_inmail_content.legal_text.static_legal_text
        html_message += sp_inmail_content.legal_text.custom_legal_text

    return TextMessageEventContent(
        msgtype=MessageType.TEXT,
        body=BeautifulSoup(html_message).text,
        format=Format.HTML,
        formatted_body=html_message,
    )
