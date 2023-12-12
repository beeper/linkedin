from typing import Any, Callable, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime

from dataclasses_json import DataClassJsonMixin, LetterCase, Undefined, config, dataclass_json
import dataclasses_json


class URN:
    def __init__(self, urn_str: str):
        urn_parts = urn_str.split(":")
        self.prefix = ":".join(urn_parts[:-1])
        self.id_parts = urn_parts[-1].strip("()").split(",")

    def get_id(self) -> str:
        assert len(self.id_parts) == 1
        return self.id_parts[0]

    def id_str(self) -> str:
        return ",".join(self.id_parts)

    def __str__(self) -> str:
        return "{}:{}".format(
            self.prefix,
            (self.id_parts[0] if len(self.id_parts) == 1 else f"({self.id_str()})"),
        )

    def __hash__(self) -> int:
        return hash(self.id_str())

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, URN):
            return False
        return self.id_parts == other.id_parts

    def __repr__(self) -> str:
        return f"URN('{str(self)}')"


# Use milliseconds instead of seconds from the UNIX epoch.
decoder_functions = {
    datetime: (lambda s: datetime.utcfromtimestamp(int(s) / 1000) if s else None),
    URN: (lambda s: URN(s) if s else None),
}
encoder_functions: dict[Any, Callable[[Any], Any]] = {
    datetime: (lambda d: int(d.timestamp() * 1000) if d else None),
    URN: (lambda u: str(u) if u else None),
}

for type_, translation_function in decoder_functions.items():
    dataclasses_json.cfg.global_config.decoders[type_] = translation_function
    dataclasses_json.cfg.global_config.decoders[
        Optional[type_]  # type: ignore
    ] = translation_function

for type_, translation_function in encoder_functions.items():
    dataclasses_json.cfg.global_config.encoders[type_] = translation_function
    dataclasses_json.cfg.global_config.encoders[
        Optional[type_]  # type: ignore
    ] = translation_function


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class Artifact:
    height: int = -1
    width: int = -1
    file_identifying_url_path_segment: str = ""
    expires_at: Optional[datetime] = None


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class VectorImage:
    artifacts: list[Artifact] = field(default_factory=list)
    root_url: str = ""


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class Picture:
    vector_image: Optional[VectorImage] = field(
        metadata=config(field_name="com.linkedin.common.VectorImage"),
        default=None,
    )


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class MiniProfile:
    entity_urn: Optional[URN] = None
    public_identifier: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    occupation: Optional[str] = None
    memorialized: bool = False
    object_urn: Optional[URN] = None
    picture: Optional[Picture] = None


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class MessagingMember:
    entity_urn: Optional[URN] = None
    mini_profile: Optional[MiniProfile] = None
    alternate_name: Optional[str] = None
    alternate_image: Optional[Picture] = None


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class Paging:
    count: int = 0
    start: int = 0
    links: list[Any] = field(default_factory=list)


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class TextEntity:
    urn: Optional[URN] = None


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class AttributeType:
    text_entity: Optional[TextEntity] = field(
        metadata=config(field_name="com.linkedin.pemberly.text.Entity"), default=None
    )


@dataclass_json
@dataclass
class Attribute:
    start: int = 0
    length: int = 0
    type_: Optional[AttributeType] = field(metadata=config(field_name="type"), default=None)


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class AttributedBody:
    text: str = ""
    attributes: list[Attribute] = field(default_factory=list)


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class MessageAttachmentCreate:
    byte_size: int = 0
    id_: Optional[URN] = field(metadata=config(field_name="id"), default=None)
    media_type: str = ""
    name: str = ""


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class MessageAttachmentReference:
    string: str = ""


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class MessageAttachment:
    id_: Optional[URN] = field(metadata=config(field_name="id"), default=None)
    byte_size: int = 0
    media_type: str = ""
    name: str = ""
    reference: Optional[MessageAttachmentReference] = None


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class AudioMetadata:
    urn: Optional[URN]
    duration: int = 0
    url: str = ""


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class MediaAttachment:
    media_type: str = ""
    audio_metadata: Optional[AudioMetadata] = None


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class GifInfo:
    original_height: int = 0
    original_width: int = 0
    url: str = ""


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class ThirdPartyMediaInfo:
    previewgif: Optional[GifInfo] = None
    nanogif: Optional[GifInfo] = None
    gif: Optional[GifInfo] = None


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class ThirdPartyMedia:
    media_type: str = ""
    id_: str = field(metadata=config(field_name="id"), default="")
    media: Optional[ThirdPartyMediaInfo] = None
    title: str = ""


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class LegalText:
    static_legal_text: str = ""
    custom_legal_text: str = ""


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class SpInmailStandardSubContent:
    action: str = ""
    action_text: str = ""


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class SpInmailSubContent:
    standard: Optional[SpInmailStandardSubContent] = field(
        metadata=config(
            field_name="com.linkedin.voyager.messaging.event.message.spinmail.SpInmailStandardSubContent"  # noqa: E501
        ),
        default=None,
    )


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class SpInmailContent:
    status: str = ""
    sp_inmail_type: str = ""
    advertiser_label: str = ""
    body: str = ""
    legal_text: Optional[LegalText] = None
    sub_content: Optional[SpInmailSubContent] = None


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class ConversationNameUpdateContent:
    new_name: str = ""


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class MessageCustomContent:
    conversation_name_update_content: Optional[ConversationNameUpdateContent] = field(
        metadata=config(
            field_name="com.linkedin.voyager.messaging.event.message.ConversationNameUpdateContent"  # noqa: E501
        ),
        default=None,
    )
    sp_inmail_content: Optional[SpInmailContent] = field(
        metadata=config(
            field_name="com.linkedin.voyager.messaging.event.message.spinmail.SpInmailContent"  # noqa: E501
        ),
        default=None,
    )
    third_party_media: Optional[ThirdPartyMedia] = field(
        metadata=config(field_name="com.linkedin.voyager.messaging.shared.ThirdPartyMedia"),
        default=None,
    )


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class CommentaryText:
    text: str = ""


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class Commentary:
    text: Optional[CommentaryText]


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class NavigationContext:
    tracking_action_type: str = ""
    action_target: str = ""


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class ArticleComponent:
    navigation_context: Optional[NavigationContext] = None


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class ImageAttributes:
    vector_image: Optional[VectorImage] = None


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class Image:
    attributes: list[ImageAttributes] = field(default_factory=list)


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class ImageComponent:
    images: list[Image] = field(default_factory=list)


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class Document:
    transcribed_document_url: str = ""


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class DocumentComponent:
    document: Optional[Document] = None


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class StreamLocations:
    url: str = ""
    expires_at: int = -1


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class ProgressiveStreams:
    width: int = -1
    height: int = -1
    size: int = -1
    media_type: str = ""
    streaming_locations: list[StreamLocations] = field(default_factory=list)


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class VideoPlayMetadata:
    progressive_streams: list[ProgressiveStreams] = field(default_factory=list)


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class VideoComponent:
    video_play_metadata: Optional[VideoPlayMetadata] = None


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class ArticleContent:
    image_component: Optional[ImageComponent] = field(
        metadata=config(field_name="com.linkedin.voyager.feed.render.ImageComponent"),
        default=None,
    )
    video_component: Optional[VideoComponent] = field(
        metadata=config(field_name="com.linkedin.voyager.feed.render.LinkedInVideoComponent"),
        default=None,
    )
    document_component: Optional[DocumentComponent] = field(
        metadata=config(field_name="com.linkedin.voyager.feed.render.DocumentComponent"),
        default=None,
    )
    article_component: Optional[ArticleComponent] = field(
        metadata=config(field_name="com.linkedin.voyager.feed.render.ArticleComponent"),
        default=None,
    )


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class ActorName:
    text: str = ""


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class Actor:
    name: Optional[ActorName] = None


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class FeedUpdate:
    actor: Optional[Actor] = None
    commentary: Optional[Commentary] = None
    content: Optional[ArticleContent] = None


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class MessageEvent:
    body: str = ""
    feed_update: Optional[FeedUpdate] = None
    message_body_render_format: str = ""
    subject: Optional[str] = None
    recalled_at: Optional[datetime] = None
    last_edited_at: Optional[datetime] = None
    attributed_body: Optional[AttributedBody] = None
    attachments: list[MessageAttachment] = field(default_factory=list)
    media_attachments: list[MediaAttachment] = field(default_factory=list)
    custom_content: Optional[MessageCustomContent] = None


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class EventContent:
    message_event: Optional[MessageEvent] = field(
        metadata=config(field_name="com.linkedin.voyager.messaging.event.MessageEvent"),
        default=None,
    )


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class From:
    messaging_member: Optional[MessagingMember] = field(
        metadata=config(field_name="com.linkedin.voyager.messaging.MessagingMember"),
        default=None,
    )


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class ReactionSummary:
    count: int = 0
    first_reacted_at: Optional[datetime] = None
    emoji: str = ""
    viewer_reacted: bool = False


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class ConversationEvent:
    created_at: Optional[datetime] = None
    entity_urn: Optional[URN] = None
    event_content: Optional[EventContent] = None
    subtype: str = ""
    from_: Optional[From] = field(metadata=config(field_name="from"), default=None)
    previous_event_in_conversation: Optional[URN] = None
    reaction_summaries: list[ReactionSummary] = field(default_factory=list)


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class Participant:
    messaging_member: Optional[MessagingMember] = field(
        metadata=config(field_name="com.linkedin.voyager.messaging.MessagingMember"),
        default=None,
    )


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class Conversation:
    group_chat: bool = False
    total_event_count: int = 0
    unread_count: int = 0
    read: Optional[bool] = None
    last_activity_at: Optional[datetime] = None
    entity_urn: Optional[URN] = None
    name: str = ""
    muted: bool = False
    events: list[ConversationEvent] = field(default_factory=list)
    participants: list[Participant] = field(default_factory=list)


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class ConversationsResponse(DataClassJsonMixin):
    elements: list[Conversation] = field(default_factory=list)
    paging: Optional[Paging] = None


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class ConversationResponse(DataClassJsonMixin):
    elements: list[ConversationEvent] = field(default_factory=list)
    paging: Optional[Paging] = None


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class MessageCreate(DataClassJsonMixin):
    attributed_body: Optional[AttributedBody] = None
    body: str = ""
    attachments: list[MessageAttachmentCreate] = field(default_factory=list)


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class MessageCreatedInfo:
    created_at: Optional[datetime] = None
    event_urn: Optional[URN] = None
    backend_event_urn: Optional[URN] = None
    conversation_urn: Optional[URN] = None
    backend_conversation_urn: Optional[URN] = None


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class SendMessageResponse(DataClassJsonMixin):
    value: Optional[MessageCreatedInfo] = None


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class UserProfileResponse(DataClassJsonMixin):
    plain_id: str = ""
    mini_profile: Optional[MiniProfile] = None


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class SeenReceipt:
    event_urn: URN
    seen_at: Optional[datetime] = None


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class RealTimeEventStreamEvent(DataClassJsonMixin):
    # Action real-time events (marking as read for example)
    action: Optional[str] = None
    conversation: Optional[Union[Conversation, URN]] = None

    # Message real-time events
    previous_event_in_conversation: Optional[URN] = None
    event: Optional[ConversationEvent] = None

    # Reaction real-time events
    reaction_added: Optional[bool] = None
    actor_mini_profile_urn: Optional[URN] = None
    event_urn: Optional[URN] = None
    reaction_summary: Optional[ReactionSummary] = None

    # Seen Receipt real-time events
    from_entity: Optional[URN] = None
    seen_receipt: Optional[SeenReceipt] = None


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class ReactorProfile:
    first_name: str = ""
    last_name: str = ""
    entity_urn: Optional[URN] = None


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class Reactor:
    reactor_urn: Optional[URN] = None
    reactor: Optional[ReactorProfile] = None


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class ReactorsResponse(DataClassJsonMixin):
    elements: list[Reactor] = field(default_factory=list)
    paging: Optional[Paging] = None


@dataclass_json(letter_case=LetterCase.CAMEL, undefined=Undefined.EXCLUDE)
@dataclass
class Error(DataClassJsonMixin, Exception):
    status: int = -1
