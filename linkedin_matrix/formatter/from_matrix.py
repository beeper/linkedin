from typing import Any, cast

from linkedin_messaging import URN
from linkedin_messaging.api_objects import (
    Attribute,
    AttributedBody,
    AttributeType,
    MessageCreate,
    TextEntity,
)
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
) -> MessageCreate:
    assert sender.li_member_urn

    attributes = []

    if content.format == Format.HTML and content.formatted_body:
        parsed = MatrixParser.parse(content.formatted_body)

        if content.msgtype == MessageType.EMOTE:
            display_name = await intent.get_displayname(sender.mxid)
            if display_name:
                parsed.prepend(f"* {display_name} ")
                attributes.append(
                    Attribute(
                        2,
                        len(display_name),
                        AttributeType(TextEntity(sender.li_member_urn)),
                    )
                )
            else:
                log.warning(f"Couldn't find displayname for {sender.mxid}")

        text = parsed.text

        for mention in parsed.entities:
            mxid = mention.extra_info["user_id"]
            user = await u.User.get_by_mxid(mxid, create=False)
            li_member_urn: URN
            if user and user.li_member_urn:
                li_member_urn = user.li_member_urn
            else:
                puppet = await pu.Puppet.get_by_mxid(mxid, create=False)
                if puppet:
                    li_member_urn = puppet.li_member_urn
                else:
                    continue
            attributes.append(
                Attribute(
                    mention.offset,
                    mention.length,
                    AttributeType(TextEntity(li_member_urn)),
                )
            )
    else:
        text = content.body
        if content.msgtype == MessageType.EMOTE:
            display_name = await intent.get_displayname(sender.mxid)
            if display_name:
                text = f"* {display_name} {text}"
                attributes.append(
                    Attribute(
                        2,
                        len(display_name),
                        AttributeType(TextEntity(sender.li_member_urn)),
                    )
                )
            else:
                log.warning(f"Couldn't find displayname for {sender.mxid}")

    return MessageCreate(AttributedBody(text, attributes), body=text)
