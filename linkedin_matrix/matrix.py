from typing import List, Union, TYPE_CHECKING
import time

from mautrix.types import (
    EventID,
    RoomID,
    UserID,
    Event,
    EventType,
    MessageEvent,
    StateEvent,
    RedactionEvent,
    PresenceEventContent,
    ReceiptEvent,
    PresenceState,
    ReactionEvent,
    ReactionEventContent,
    RelationType,
    PresenceEvent,
    TypingEvent,
    TextMessageEventContent,
    MessageType,
    EncryptedEvent,
    SingleReceiptEventContent,
)
from mautrix.errors import MatrixError
from mautrix.bridge import BaseMatrixHandler

from . import user as u, portal as po, puppet as pu

if TYPE_CHECKING:
    from .__main__ import LinkedInBridge


class MatrixHandler(BaseMatrixHandler):
    def __init__(self, bridge: "LinkedInBridge") -> None:
        prefix, suffix = (
            bridge.config["bridge.username_template"].format(userid=":").split(":")
        )
        homeserver = bridge.config["homeserver.domain"]
        self.user_id_prefix = f"@{prefix}"
        self.user_id_suffix = f"{suffix}:{homeserver}"
        super().__init__(bridge=bridge)

    async def send_welcome_message(self, room_id: RoomID, inviter: "u.User") -> None:
        await super().send_welcome_message(room_id, inviter)
        if not inviter.notice_room:
            inviter.notice_room = room_id
            await inviter.save()
            await self.az.intent.send_notice(
                room_id,
                "This room has been marked as your LinkedIn Messages bridge notice "
                "room.",
            )

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
