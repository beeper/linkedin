from typing import cast, Optional, TYPE_CHECKING, Union

from mautrix.bridge import BaseMatrixHandler
from mautrix.types import (
    EncryptedEvent,
    Event,
    EventID,
    EventType,
    MessageEvent,
    PresenceEvent,
    PresenceEventContent,
    ReactionEvent,
    ReceiptEvent,
    RedactionEvent,
    RoomID,
    StateEvent,
    TypingEvent,
    UserID,
)
from mautrix.types.event.message import RelationType
from mautrix.types.event.reaction import ReactionEventContent

# these have to be in this particular order to avoid circular imports
from . import user as u, portal as po, puppet as pu  # noqa: I101

if TYPE_CHECKING:
    from .__main__ import LinkedInBridge


class MatrixHandler(BaseMatrixHandler):
    def __init__(self, bridge: "LinkedInBridge"):
        prefix, suffix = (
            bridge.config["bridge.username_template"].format(userid=":").split(":")
        )
        homeserver = bridge.config["homeserver.domain"]
        self.user_id_prefix = f"@{prefix}"
        self.user_id_suffix = f"{suffix}:{homeserver}"
        super().__init__(bridge=bridge)

    async def send_welcome_message(self, room_id: RoomID, inviter: "u.User"):
        await super().send_welcome_message(room_id, inviter)
        if not inviter.notice_room:
            inviter.notice_room = room_id
            await inviter.save()
            await self.az.intent.send_notice(
                room_id,
                "This room has been marked as your LinkedIn Messages bridge notice "
                "room.",
            )

    async def handle_read_receipt(self, user: "u.User", portal: "po.Portal", *_):
        if not user.client or not portal.mxid:
            return
        self.log.debug(f"{user.li_member_urn} read {portal.li_thread_urn}")
        await user.client.mark_conversation_as_read(portal.li_thread_urn)

    def filter_matrix_event(self, evt: Event) -> bool:
        if isinstance(evt, (ReceiptEvent, TypingEvent, PresenceEvent)):
            return False
        elif not isinstance(
            evt,
            (ReactionEvent, RedactionEvent, MessageEvent, StateEvent, EncryptedEvent),
        ):
            return True
        return (
            evt.sender == self.az.bot_mxid
            or pu.Puppet.get_id_from_mxid(evt.sender) is not None
        )

    async def handle_leave(self, room_id: RoomID, user_id: UserID, _):
        portal = await po.Portal.get_by_mxid(room_id)
        if not portal:
            return

        user = await u.User.get_by_mxid(user_id, create=False)
        if not user:
            return

        await portal.handle_matrix_leave(user)

    @staticmethod
    async def handle_redaction(
        room_id: RoomID,
        user_id: UserID,
        event_id: EventID,
        redaction_event_id: EventID,
    ):
        user = await u.User.get_by_mxid(user_id)
        if not user:
            return

        portal = await po.Portal.get_by_mxid(room_id)
        if not portal:
            return

        await portal.handle_matrix_redaction(user, event_id, redaction_event_id)

    @classmethod
    async def handle_reaction(
        cls,
        room_id: RoomID,
        user_id: UserID,
        event_id: EventID,
        content: ReactionEventContent,
    ):
        if content.relates_to.rel_type != RelationType.ANNOTATION:
            cls.log.debug(
                f"Ignoring m.reaction event in {room_id} from {user_id} with "
                f"unexpected relation type {content.relates_to.rel_type}"
            )
            return
        user = await u.User.get_by_mxid(user_id)
        if not user:
            return

        portal = await po.Portal.get_by_mxid(room_id)
        if not portal:
            return

        await portal.handle_matrix_reaction(
            user, event_id, content.relates_to.event_id, content.relates_to.key
        )

    async def handle_presence(self, user_id: UserID, info: PresenceEventContent):
        # TODO (#50)
        self.log.info(f"user ({user_id}) is present {info}")
        if not self.config["bridge.presence"]:
            return

    async def handle_typing(self, room_id: RoomID, typing: list[UserID]):
        self.log.info(f"room: {room_id}: typing {typing}")
        portal: Optional[po.Portal] = await po.Portal.get_by_mxid(room_id)
        if not portal:
            return
        # https://www.linkedin.com/voyager/api/messaging/conversations?action=typing
        # {"conversationId":"2-ZmRhMGVmZDYtNDVjYS00Y2Y2LWE3ZTYtNmFkM2FlMGMxMDA1XzAxMg=="}

    async def handle_ephemeral_event(
        self,
        evt: Union[ReceiptEvent, PresenceEvent, TypingEvent],
    ):
        if evt.type == EventType.PRESENCE:
            evt = cast(PresenceEvent, evt)
            await self.handle_presence(evt.sender, evt.content)
        elif evt.type == EventType.TYPING:
            evt = cast(TypingEvent, evt)
            await self.handle_typing(evt.room_id, evt.content.user_ids)
        elif evt.type == EventType.RECEIPT:
            await self.handle_receipt(cast(ReceiptEvent, evt))

    async def handle_event(self, evt: Event):
        if evt.type == EventType.ROOM_REDACTION:
            await self.handle_redaction(
                evt.room_id, evt.sender, evt.redacts, evt.event_id
            )
        elif evt.type == EventType.REACTION:
            await self.handle_reaction(
                evt.room_id, evt.sender, evt.event_id, evt.content
            )
