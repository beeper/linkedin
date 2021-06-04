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

from . import user as u, portal as po

# from .db import ThreadType, Message as DBMessage

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
