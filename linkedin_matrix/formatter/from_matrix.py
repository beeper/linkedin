from dataclasses import dataclass
from typing import Any, cast, Dict, List

from mautrix.appservice import IntentAPI
from mautrix.types import Format, MessageType, TextMessageEventContent
from mautrix.util.formatter import (
    EntityString,
    EntityType,
    MarkdownString,
    MatrixParser as BaseMatrixParser,
    SimpleEntity,
)
from mautrix.util.logging import TraceLogger

from .. import puppet as pu, user as u


# TODO move a lot of these classes to linkedin-api
@dataclass
class Mention:
    start: int
    length: int
    urn: str

    def to_json(self) -> Dict[str, Any]:
        return {
            "start": self.start,
            "length": self.length,
            "type": {
                "com.linkedin.pemberly.text.Entity": {
                    "urn": f"urn:li:fs_miniProfile:{self.urn}"
                }
            },
        }


@dataclass
class SendParams:
    text: str
    mentions: List[Mention]


class LinkedInFormatString(EntityString[SimpleEntity, EntityType], MarkdownString):
    def format(self, entity_type: EntityType, **kwargs: Any) -> "LinkedInFormatString":
        prefix = suffix = ""

        if entity_type == EntityType.USER_MENTION:
            self.entities.append(
                SimpleEntity(
                    type=entity_type,
                    offset=0,
                    length=len(self.text),
                    extra_info={"user_id": kwargs["user_id"]},
                )
            )
            return self
        elif entity_type == EntityType.URL:
            if kwargs["url"] != self.text:
                suffix = f" ({kwargs['url']})"
        elif entity_type == EntityType.PREFORMATTED:
            prefix = "```\n"
            suffix = "```"
        elif entity_type == EntityType.INLINE_CODE:
            prefix = suffix = "`"
        elif entity_type == EntityType.BLOCKQUOTE:
            children = self.trim().split("\n")
            children = [child.prepend("> ") for child in children]
            return self.join(children, "\n")
        else:
            return self

        self._offset_entities(len(prefix))
        self.text = f"{prefix}{self.text}{suffix}"
        return self


class MatrixParser(BaseMatrixParser[LinkedInFormatString]):
    fs = LinkedInFormatString

    @classmethod
    def parse(cls, data: str) -> LinkedInFormatString:
        return cast(LinkedInFormatString, super().parse(data))


async def matrix_to_linkedin(
    content: TextMessageEventContent,
    sender: "u.User",
    intent: IntentAPI,
    log: TraceLogger,
) -> SendParams:
    mentions = []

    if content.format == Format.HTML and content.formatted_body:
        parsed = MatrixParser.parse(content.formatted_body)

        if content.msgtype == MessageType.EMOTE:
            display_name = await intent.get_displayname(sender.mxid)
            if display_name:
                parsed.prepend(f"* {display_name} ")
                mentions.append(Mention(2, len(display_name), sender.li_member_urn))
            else:
                log.warning(f"Couldn't find displayname for {sender.mxid}")

        text = parsed.text

        for mention in parsed.entities:
            mxid = mention.extra_info["user_id"]
            user = await u.User.get_by_mxid(mxid, create=False)
            if user and user.li_member_urn:
                li_member_urn = user.li_member_urn
            else:
                puppet = await pu.Puppet.get_by_mxid(mxid, create=False)
                if puppet:
                    li_member_urn = puppet.li_member_urn
                else:
                    continue
            mentions.append(Mention(mention.offset, mention.length, li_member_urn))
    else:
        text = content.body

    return SendParams(text, mentions)
