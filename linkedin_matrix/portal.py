import asyncio
from collections import deque
from datetime import datetime
from io import BytesIO
from typing import Any, AsyncGenerator, cast, Optional, TYPE_CHECKING, Union

import magic
from linkedin_messaging import URN
from linkedin_messaging.api_objects import (
    AttributedBody,
    Conversation,
    ConversationEvent,
    Error,
    MessageAttachment,
    MessageCreate,
    MiniProfile,
    ReactionSummary,
    RealTimeEventStreamEvent,
    ThirdPartyMedia,
)
from mautrix.appservice import IntentAPI
from mautrix.bridge import async_getter_lock, BasePortal, NotificationDisabler
from mautrix.errors import MatrixError, MForbidden
from mautrix.types import (
    AudioInfo,
    ContentURI,
    EncryptedFile,
    EventID,
    EventType,
    FileInfo,
    ImageInfo,
    MediaMessageEventContent,
    Membership,
    MessageEventContent,
    MessageType,
    RoomID,
    TextMessageEventContent,
    VideoInfo,
)
from mautrix.types.primitive import UserID
from mautrix.util.simple_lock import SimpleLock

from . import puppet as p, user as u
from .config import Config
from .db import (
    Message as DBMessage,
    Portal as DBPortal,
    Reaction as DBReaction,
)
from .formatter import (
    linkedin_spinmail_to_matrix,
    linkedin_subject_to_matrix,
    linkedin_to_matrix,
    matrix_to_linkedin,
)

if TYPE_CHECKING:
    from .__main__ import LinkedInBridge
    from .matrix import MatrixHandler

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    from mautrix.crypto.attachments import decrypt_attachment, encrypt_attachment
except ImportError:
    decrypt_attachment = encrypt_attachment = None  # type: ignore


class FakeLock:
    async def __aenter__(self):
        pass

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any):
        pass


StateBridge = EventType.find("m.bridge", EventType.Class.STATE)
StateHalfShotBridge = EventType.find("uk.half-shot.bridge", EventType.Class.STATE)
MediaInfo = Union[FileInfo, VideoInfo, AudioInfo, ImageInfo]


class Portal(DBPortal, BasePortal):
    invite_own_puppet_to_pm: bool = False
    by_mxid: dict[RoomID, "Portal"] = {}
    by_li_thread_urn: dict[tuple[URN, Optional[URN]], "Portal"] = {}
    matrix: "MatrixHandler"
    config: Config

    backfill_lock: SimpleLock
    _dedup: deque[URN]
    _send_locks: dict[URN, asyncio.Lock]
    _noop_lock: FakeLock = FakeLock()

    def __init__(
        self,
        li_thread_urn: URN,
        li_receiver_urn: Optional[URN],
        li_is_group_chat: bool,
        li_other_user_urn: Optional[URN] = None,
        mxid: Optional[RoomID] = None,
        name: Optional[str] = None,
        photo_id: Optional[str] = None,
        avatar_url: Optional[ContentURI] = None,
        topic: Optional[str] = None,
        encrypted: bool = False,
    ):
        super().__init__(
            li_thread_urn,
            li_receiver_urn,
            li_is_group_chat,
            li_other_user_urn,
            mxid,
            encrypted,
            name,
            photo_id,
            avatar_url,
            topic,
        )
        self.log = self.log.getChild(self.li_urn_log)

        self._main_intent = None
        self._create_room_lock = asyncio.Lock()
        self._dedup = deque(maxlen=100)
        self._send_locks = {}
        self._typing = set()

        self.backfill_lock = SimpleLock(
            "Waiting for backfilling to finish before handling %s", log=self.log
        )
        self._backfill_leave: Optional[set[IntentAPI]] = None

    @classmethod
    def init_cls(cls, bridge: "LinkedInBridge"):
        BasePortal.bridge = bridge
        cls.az = bridge.az
        cls.config = bridge.config
        cls.loop = bridge.loop
        cls.matrix = bridge.matrix
        cls.invite_own_puppet_to_pm = cls.config["bridge.invite_own_puppet_to_pm"]
        NotificationDisabler.puppet_cls = p.Puppet
        NotificationDisabler.config_enabled = cls.config[
            "bridge.backfill.disable_notifications"
        ]

    # region DB conversion

    async def delete(self):
        if self.mxid:
            await DBMessage.delete_all_by_room(self.mxid)
            self.by_mxid.pop(self.mxid, None)
        self.by_li_thread_urn.pop(self.li_urn_full, None)
        await super().delete()

    # endregion

    # region Send lock handling

    def require_send_lock(self, li_member_urn: URN) -> asyncio.Lock:
        try:
            lock = self._send_locks[li_member_urn]
        except KeyError:
            lock = asyncio.Lock()
            self._send_locks[li_member_urn] = lock
        return lock

    def optional_send_lock(self, li_member_urn: URN) -> Union[asyncio.Lock, FakeLock]:
        try:
            return self._send_locks[li_member_urn]
        except KeyError:
            pass
        return self._noop_lock

    # endregion

    # region Properties

    @property
    def li_urn_full(self) -> tuple[URN, Optional[URN]]:
        return self.li_thread_urn, self.li_receiver_urn

    @property
    def main_intent(self) -> IntentAPI:
        if not self._main_intent:
            raise ValueError(
                "Portal must be postinit()ed before main_intent can be used"
            )
        return self._main_intent

    @property
    def is_direct(self) -> bool:
        return not self.li_is_group_chat

    @property
    def li_urn_log(self) -> str:
        if self.is_direct:
            return f"{self.li_thread_urn}<->{self.li_receiver_urn}"
        return str(self.li_thread_urn)

    # endregion

    # region Database getters

    async def postinit(self):
        self.by_li_thread_urn[self.li_urn_full] = self
        if self.mxid:
            self.by_mxid[self.mxid] = self

        if self.is_direct:
            if not self.li_other_user_urn:
                raise ValueError("Portal.li_other_user_urn not set for private chat")
            self._main_intent = (
                await p.Puppet.get_by_li_member_urn(self.li_other_user_urn)
            ).default_mxid_intent
        else:
            self._main_intent = self.az.intent

    @classmethod
    @async_getter_lock
    async def get_by_mxid(cls, mxid: RoomID) -> Optional["Portal"]:
        try:
            return cls.by_mxid[mxid]
        except KeyError:
            pass

        portal = cast("Portal", await super().get_by_mxid(mxid))
        if portal:
            await portal.postinit()
            return portal

        return None

    @classmethod
    @async_getter_lock
    async def get_by_li_thread_urn(
        cls,
        li_thread_urn: URN,
        *,
        li_receiver_urn: URN = None,
        li_is_group_chat: bool = False,
        li_other_user_urn: URN = None,
        create: bool = True,
    ) -> Optional["Portal"]:
        try:
            return cls.by_li_thread_urn[(li_thread_urn, li_receiver_urn)]
        except KeyError:
            pass

        portal = cast(
            Portal,
            await super().get_by_li_thread_urn(li_thread_urn, li_receiver_urn),
        )
        if portal:
            await portal.postinit()
            return portal

        if create:
            portal = cls(
                li_thread_urn,
                li_receiver_urn=li_receiver_urn,
                li_is_group_chat=li_is_group_chat,
                li_other_user_urn=li_other_user_urn,
            )
            await portal.insert()
            await portal.postinit()
            return portal

        return None

    @classmethod
    async def get_all_by_li_receiver_urn(
        cls,
        li_receiver_urn: URN,
    ) -> AsyncGenerator["Portal", None]:
        portals = await super().get_all_by_li_receiver_urn(li_receiver_urn)
        for portal in portals:
            portal = cast(Portal, portal)
            try:
                yield cls.by_li_thread_urn[
                    (portal.li_thread_urn, portal.li_receiver_urn)
                ]
            except KeyError:
                await portal.postinit()
                yield portal

    @classmethod
    async def all(cls) -> AsyncGenerator["Portal", None]:
        portals = await super().all()
        for portal in cast(list[Portal], portals):
            try:
                yield cls.by_li_thread_urn[
                    (portal.li_thread_urn, portal.li_receiver_urn)
                ]
            except KeyError:
                await portal.postinit()
                yield portal

    # endregion

    # region Chat info updating

    async def update_info(
        self,
        source: Optional["u.User"] = None,
        conversation: Optional[Conversation] = None,
    ):
        if not conversation:
            # shouldn't happen currently
            assert False, "update_info called without conversation"

        if conversation.entity_urn != self.li_thread_urn:
            self.log.warning(
                f"Got different ID ({conversation.entity_urn}) than what was asked "
                f"for ({self.li_thread_urn}) when fetching"
            )

        changed = False
        if self.is_direct:
            if (
                len(conversation.participants)
                and (mm := conversation.participants[0].messaging_member)
                and (mp := mm.mini_profile)
            ):
                changed = await self._update_topic(mp) or changed
        else:
            changed = await self._update_name(conversation.name) or changed

        changed = await self._update_participants(source, conversation) or changed
        if changed:
            await self.update_bridge_info()
            await self.save()

    async def _update_name(self, name: str) -> bool:
        if not name:
            self.log.warning("Got empty name in _update_name call")
            return False
        if self.name != name:
            self.log.trace("Updating name %s -> %s", self.name, name)
            self.name = name
            if self.mxid and (self.encrypted or not self.is_direct):
                await self.main_intent.set_room_name(self.mxid, self.name)
            return True
        return False

    async def _update_photo_from_puppet(self, puppet: "p.Puppet") -> bool:
        if self.photo_id == puppet.photo_id:
            return False
        self.photo_id = puppet.photo_id
        if puppet.photo_mxc:
            self.avatar_url = puppet.photo_mxc
        elif self.photo_id:
            profile = await self.main_intent.get_profile(puppet.default_mxid)
            self.avatar_url = profile.avatar_url
            puppet.photo_mxc = profile.avatar_url
        else:
            self.avatar_url = ContentURI("")
        if self.mxid:
            await self.main_intent.set_room_avatar(self.mxid, self.avatar_url)
        return True

    async def _update_topic(self, mini_profile: MiniProfile) -> bool:
        if not self.config["bridge.set_topic_on_dms"]:
            return False

        topic_parts = [
            part
            for part in [
                mini_profile.occupation,
                (
                    f"https://www.linkedin.com/in/{mini_profile.public_identifier}"
                    if (
                        mini_profile.public_identifier
                        and mini_profile.public_identifier != "UNKNOWN"
                    )
                    else None
                ),
            ]
            if part
        ]
        topic = " | ".join(topic_parts) if len(topic_parts) else None
        if topic == self.topic:
            return False
        self.topic = topic

        if self.mxid:
            await self.main_intent.set_room_topic(self.mxid, self.topic or "")

        return True

    async def update_bridge_info(self):
        if not self.mxid:
            self.log.debug("Not updating bridge info: no Matrix room created")
            return
        try:
            self.log.debug("Updating bridge info...")
            await self.main_intent.send_state_event(
                self.mxid,
                StateBridge,
                self.bridge_info,
                self.bridge_info_state_key,
            )
            # TODO (#52) remove this once
            # https://github.com/matrix-org/matrix-doc/pull/2346 is in spec
            await self.main_intent.send_state_event(
                self.mxid,
                StateHalfShotBridge,
                self.bridge_info,
                self.bridge_info_state_key,
            )
        except Exception:
            self.log.warning("Failed to update bridge info", exc_info=True)

    async def _update_participants(
        self,
        source: "u.User",
        conversation: Optional[Conversation] = None,
    ) -> bool:
        changed = False

        for participant in conversation.participants if conversation else []:
            if (
                not (mm := participant.messaging_member)
                or not (mp := mm.mini_profile)
                or not (entity_urn := mp.entity_urn)
            ):
                self.log.error(f"No entity_urn on participant! {participant}")
                continue
            participant_urn = entity_urn
            if participant_urn == URN("UNKNOWN"):
                participant_urn = conversation.entity_urn
            puppet = await p.Puppet.get_by_li_member_urn(participant_urn)
            await puppet.update_info(source, participant.messaging_member)
            if (
                self.is_direct
                and self.li_other_user_urn == puppet.li_member_urn
                and self.encrypted
            ):
                changed = await self._update_name(puppet.name) or changed
                changed = await self._update_photo_from_puppet(puppet) or changed

            if self.mxid:
                if puppet.li_member_urn != self.li_receiver_urn or puppet.is_real_user:
                    await puppet.intent_for(self).ensure_joined(
                        self.mxid, bot=self.main_intent
                    )

        return changed

    # endregion

    # region Matrix room creation

    async def create_matrix_room(
        self,
        source: "u.User",
        conversation: Optional[Conversation] = None,
    ) -> Optional[RoomID]:
        if self.mxid:
            try:
                await self._update_matrix_room(source, conversation)
            except Exception:
                self.log.exception("Failed to update portal")
            return self.mxid

        async with self._create_room_lock:
            try:
                return await self._create_matrix_room(source, conversation)
            except Exception:
                self.log.exception("Failed to create portal")
                return None

    async def update_matrix_room(
        self,
        source: "u.User",
        conversation: Optional[Conversation] = None,
    ):
        try:
            await self._update_matrix_room(source, conversation)
        except Exception:
            self.log.exception("Failed to update portal")

    async def _create_matrix_room(
        self,
        source: "u.User",
        conversation: Optional[Conversation] = None,
    ) -> Optional[RoomID]:
        if self.mxid:
            await self._update_matrix_room(source, conversation)
            return self.mxid

        self.log.debug("Creating Matrix room")
        name: Optional[str] = None
        initial_state = [
            {
                "type": str(StateBridge),
                "state_key": self.bridge_info_state_key,
                "content": self.bridge_info,
            },
            {
                # TODO (#52) remove this once
                # https://github.com/matrix-org/matrix-doc/pull/2346 is in spec
                "type": str(StateHalfShotBridge),
                "state_key": self.bridge_info_state_key,
                "content": self.bridge_info,
            },
        ]
        invites = [source.mxid]
        if self.config["bridge.encryption.default"] and self.matrix.e2ee:
            self.encrypted = True
            initial_state.append(
                {
                    "type": "m.room.encryption",
                    "content": {"algorithm": "m.megolm.v1.aes-sha2"},
                }
            )
            if self.is_direct:
                invites.append(self.az.bot_mxid)

        await self.update_info(source, conversation)

        if self.topic:
            initial_state.append(
                {
                    "type": str(EventType.ROOM_TOPIC),
                    "content": {"topic": self.topic},
                }
            )

        # if not info:
        #     self.log.debug(
        #         "update_info() didn't return info, cancelling room creation")
        #     return None

        if self.encrypted or not self.is_direct:
            name = self.name
            initial_state.append(
                {
                    "type": str(EventType.ROOM_AVATAR),
                    "content": {"avatar_url": self.avatar_url},
                }
            )

        # We lock backfill lock here so any messages that come between the room being
        # created and the initial backfill finishing wouldn't be bridged before the
        # backfill messages.
        with self.backfill_lock:
            self.mxid = await self.main_intent.create_room(
                name=name,
                is_direct=self.is_direct,
                initial_state=initial_state,
                invitees=invites,
            )
            if not self.mxid:
                raise Exception("Failed to create room: no mxid returned")

            if self.encrypted and self.matrix.e2ee and self.is_direct:
                try:
                    await self.az.intent.ensure_joined(self.mxid)
                except Exception:
                    self.log.warning(
                        f"Failed to add bridge bot to new private chat {self.mxid}"
                    )

            await self.save()
            self.log.debug(f"Matrix room created: {self.mxid}")
            self.by_mxid[self.mxid] = self

            if not self.is_direct:
                await self._update_participants(source, conversation)
            else:
                if (
                    (mm := conversation.participants[0].messaging_member)
                    and (mp := mm.mini_profile)
                    and (mp.entity_urn == URN("UNKNOWN"))
                ):
                    levels = await self.main_intent.get_power_levels(self.mxid)
                    if levels.get_user_level(self.main_intent.mxid) == 100:
                        levels.events_default = 50
                        await self.main_intent.set_power_levels(self.mxid, levels)

                puppet = await p.Puppet.get_by_custom_mxid(source.mxid)
                if puppet:
                    try:
                        did_join = await puppet.intent.join_room_by_id(self.mxid)
                        if did_join:
                            await source.update_direct_chats(
                                {self.main_intent.mxid: [self.mxid]}
                            )
                    except MatrixError:
                        self.log.debug(
                            "Failed to join custom puppet into newly created portal",
                            exc_info=True,
                        )

            try:
                await self.backfill(source, conversation, is_initial=True)
            except Exception:
                self.log.exception("Failed to backfill new portal")

            # await self._sync_read_receipts(info.read_receipts.nodes)

        return self.mxid

    async def _update_matrix_room(
        self,
        source: "u.User",
        conversation: Optional[Conversation] = None,
    ):
        await self.main_intent.invite_user(self.mxid, source.mxid, check_cache=False)
        puppet = await p.Puppet.get_by_custom_mxid(source.mxid)
        if puppet and puppet.is_real_user:
            await puppet.intent.ensure_joined(self.mxid)
        await self.update_info(source, conversation)

    @property
    def bridge_info_state_key(self) -> str:
        return f"com.github.linkedin://linkedin/{self.li_thread_urn.id_str()}"

    @property
    def bridge_info(self) -> dict[str, Any]:
        return {
            "bridgebot": self.az.bot_mxid,
            "creator": self.main_intent.mxid,
            "protocol": {
                "id": "linkedin",
                "displayname": "LinkedIn Messages",
                "avatar_url": self.config["appservice.bot_avatar"],
            },
            "channel": {
                "id": self.li_thread_urn.id_str(),
                "displayname": self.name,
                "avatar_url": self.avatar_url,
            },
        }

    # endregion

    # region Event backfill

    async def backfill(
        self,
        source: "u.User",
        conversation: Optional[Conversation],
        is_initial: bool,
    ):
        assert self.li_receiver_urn
        limit: Optional[int] = (
            self.config["bridge.backfill.initial_limit"]
            if is_initial
            else self.config["bridge.backfill.missed_limit"]
        )
        if limit == 0:
            return
        elif limit and limit < 0:
            limit = None
        last_active = None

        if not is_initial and conversation and len(conversation.events) > 0:
            last_active = conversation.events[-1].created_at

        most_recent = await DBMessage.get_most_recent(
            self.li_thread_urn, self.li_receiver_urn
        )
        if most_recent and is_initial:
            self.log.debug(
                f"Not backfilling {self.li_urn_log}: already bridged messages found"
            )
        elif (not most_recent or not most_recent.timestamp) and not is_initial:
            self.log.debug(
                f"Not backfilling {self.li_urn_log}: no most recent message found"
            )
        elif last_active and most_recent and most_recent.timestamp >= last_active:
            self.log.debug(
                f"Not backfilling {self.li_urn_log}: last activity is equal to most "
                f"recent bridged message ({most_recent.timestamp} >= {last_active})"
            )
        elif conversation:
            with self.backfill_lock:
                await self._backfill(
                    source,
                    limit,
                    most_recent.timestamp if most_recent else None,
                    conversation=conversation,
                )

    async def _backfill(
        self,
        source: "u.User",
        limit: Optional[int],
        after_timestamp: Optional[datetime],
        conversation: Conversation,
    ):
        assert self.mxid
        assert conversation.entity_urn
        assert source.client, f"No client found for {source.mxid}!"
        self.log.debug(f"Backfilling history through {source.mxid}")
        messages = conversation.events

        if len(messages):
            oldest_message = messages[0]
            before_timestamp = oldest_message.created_at
        else:
            before_timestamp = datetime.now()

        self.log.debug(
            f"Fetching up to {limit} messages through {source.li_member_urn}"
        )

        while limit is None or len(messages) < limit:
            result = await source.client.get_conversation(
                conversation.entity_urn,
                created_before=before_timestamp,
            )
            elements = result.elements
            messages = elements + messages

            if len(elements) < 20:
                break

            if (
                len(elements)
                and elements[0].created_at
                and after_timestamp
                and (created_at := elements[0].created_at) <= after_timestamp
            ):
                self.log.debug(
                    f"Stopping fetching messages at {created_at} as message is older "
                    f"than newest bridged message ({created_at} < {after_timestamp})",
                )
                break

            before_timestamp = messages[0].created_at

        if after_timestamp:
            try:
                slice_index = next(
                    index
                    for index, message in enumerate(messages)
                    if message.created_at and message.created_at > after_timestamp
                )
                messages = messages[slice_index:]
            except StopIteration:
                messages = []

        if limit and len(messages) > limit:
            messages = messages[-limit:]

        self._backfill_leave = set()
        async with NotificationDisabler(self.mxid, source):
            for message in messages:
                if (
                    not (f := message.from_)
                    or not (mm := f.messaging_member)
                    or not (mp := mm.mini_profile)
                    or not (entity_urn := mp.entity_urn)
                ):
                    self.log.error(
                        "No entity_urn found on message mini_profile!", message
                    )
                    continue
                member_urn = entity_urn
                if member_urn == URN("UNKNOWN"):
                    member_urn = conversation.entity_urn
                puppet = await p.Puppet.get_by_li_member_urn(member_urn)
                await self.handle_linkedin_message(source, puppet, message)
        for intent in self._backfill_leave:
            self.log.trace(f"Leaving room with {intent.mxid} post-backfill")
            await intent.leave_room(self.mxid)
        self.log.info(f"Backfilled {len(messages)} messages through {source.mxid}")

    # endregion

    # region Matrix event handling

    async def _send_delivery_receipt(self, event_id: EventID):
        if event_id and self.config["bridge.delivery_receipts"] and self.mxid:
            try:
                await self.az.intent.mark_read(self.mxid, event_id)
            except Exception:
                self.log.exception(f"Failed to send delivery receipt for {event_id}")

    async def _send_bridge_error(self, msg: str, certain_failure: bool = False):
        certainty = "was not" if certain_failure else "may not have been"
        await self._send_message(
            self.main_intent,
            TextMessageEventContent(
                msgtype=MessageType.NOTICE,
                body=f"\u26a0 Your message {certainty} bridged: {msg}",
            ),
        )

    async def handle_matrix_leave(self, user: "u.User"):
        if self.is_direct:
            self.log.info(
                f"{user.mxid} left private chat portal with {self.li_other_user_urn}"
            )
            if user.li_member_urn == self.li_receiver_urn:
                self.log.info(
                    f"{user.mxid} was the recipient of this portal. "
                    "Cleaning up and deleting..."
                )
                await self.cleanup_and_delete()
        else:
            self.log.debug(f"{user.mxid} left portal to {self.li_other_user_urn}")

    async def handle_matrix_message(
        self,
        sender: "u.User",
        message: MessageEventContent,
        event_id: EventID,
    ):
        try:
            await self._handle_matrix_message(sender, message, event_id)
        except Error as e:
            self.log.exception(f"Failed handling {event_id}: {e.to_json()}")
            await self._send_bridge_error(e.to_json())
        except Exception as e:
            self.log.exception(f"Failed handling {event_id}")
            await self._send_bridge_error(str(e))

    async def _handle_matrix_message(
        self,
        sender: "u.User",
        message: MessageEventContent,
        event_id: EventID,
    ):
        if message.get(
            self.az.real_user_content_key, False
        ) and await p.Puppet.get_by_custom_mxid(sender.mxid):
            self.log.debug(
                f"Ignoring puppet-sent message by confirmed puppet user {sender.mxid}"
            )
            return

        if message.msgtype in (MessageType.TEXT, MessageType.NOTICE, MessageType.EMOTE):
            await self._handle_matrix_text(
                event_id,
                sender,
                cast(TextMessageEventContent, message),
            )
        elif message.msgtype.is_media:
            await self._handle_matrix_media(
                event_id,
                sender,
                cast(MediaMessageEventContent, message),
            )
        else:
            self.log.warning(f"Unsupported msgtype {message.msgtype} in {event_id}")
            await self._send_bridge_error(
                f"messages of {message.msgtype} are not supported.",
                certain_failure=True,
            )
            return

    async def _send_linkedin_message(
        self,
        event_id: EventID,
        sender: "u.User",
        message_create: MessageCreate,
    ) -> DBMessage:
        assert self.mxid
        assert self.li_receiver_urn
        assert sender.client
        assert sender.li_member_urn

        async with self.require_send_lock(sender.li_member_urn):
            resp = await sender.client.send_message(self.li_thread_urn, message_create)
            if not resp.value or not resp.value.event_urn:
                raise Exception("Response value was None.")

            message = DBMessage(
                mxid=event_id,
                mx_room=self.mxid,
                li_message_urn=resp.value.event_urn,
                li_thread_urn=self.li_thread_urn,
                li_sender_urn=sender.li_member_urn,
                li_receiver_urn=self.li_receiver_urn,
                index=0,
                timestamp=datetime.now(),
            )
            await self._send_delivery_receipt(event_id)
            self._dedup.append(resp.value.event_urn)
            await message.insert()
            return message

    async def _handle_matrix_text(
        self,
        event_id: EventID,
        sender: "u.User",
        message: TextMessageEventContent,
    ):
        assert sender.client
        message_create = await matrix_to_linkedin(
            message, sender, self.main_intent, self.log
        )
        await self._send_linkedin_message(event_id, sender, message_create)

    async def _handle_matrix_media(
        self,
        event_id: EventID,
        sender: "u.User",
        message: MediaMessageEventContent,
    ):
        assert sender.client
        if not message.info:
            return

        if message.file and message.file.url and decrypt_attachment:
            data = await self.main_intent.download_media(message.file.url)
            file_hash = message.file.hashes.get("sha256")
            if file_hash:
                data = decrypt_attachment(
                    data,
                    message.file.key.key,
                    file_hash,
                    message.file.iv,
                )
            else:
                return
        elif message.url:
            data = await self.main_intent.download_media(message.url)
        else:
            return

        attachment = await sender.client.upload_media(
            data, message.body, message.info.mimetype
        )
        attachment.media_type = attachment.media_type or ""
        await self._send_linkedin_message(
            event_id,
            sender,
            MessageCreate(AttributedBody(), attachments=[attachment]),
        )

    async def handle_matrix_redaction(
        self,
        sender: "u.User",
        event_id: EventID,
        redaction_event_id: EventID,
    ):
        if not self.mxid or not sender.client:
            return

        message = await DBMessage.get_by_mxid(event_id, self.mxid)
        if message:
            try:
                await message.delete()
                await sender.client.delete_message(
                    self.li_thread_urn, message.li_message_urn
                )
            except Exception:
                self.log.exception("Delete message failed")

        reaction = await DBReaction.get_by_mxid(event_id, self.mxid)
        if reaction:
            try:
                await reaction.delete()
                await sender.client.remove_emoji_reaction(
                    self.li_thread_urn, reaction.li_message_urn, emoji=reaction.reaction
                )
            except Exception:
                self.log.exception("Removing reaction failed")

        await self._send_delivery_receipt(redaction_event_id)

    async def handle_matrix_reaction(
        self,
        sender: "u.User",
        event_id: EventID,
        reacting_to: EventID,
        reaction: str,
    ):
        if not sender.li_member_urn or not self.mxid or not sender.client:
            return
        async with self.require_send_lock(sender.li_member_urn):
            message = await DBMessage.get_by_mxid(reacting_to, self.mxid)
            if not message:
                self.log.debug(f"Ignoring reaction to unknown event {reacting_to}")
                return

            await sender.client.add_emoji_reaction(
                self.li_thread_urn, message.li_message_urn, reaction
            )
            await DBReaction(
                mxid=event_id,
                mx_room=message.mx_room,
                li_message_urn=message.li_message_urn,
                li_receiver_urn=self.li_receiver_urn,
                li_sender_urn=sender.li_member_urn,
                reaction=reaction,
            ).insert()

        await self._send_delivery_receipt(event_id)

    # endregion

    # region LinkedIn event handling

    async def _bridge_own_message_pm(
        self,
        source: "u.User",
        sender: "p.Puppet",
        mid: str,
        invite: bool = True,
    ) -> bool:
        assert self.mxid
        if (
            self.is_direct
            and sender.li_member_urn == source.li_member_urn
            and not sender.is_real_user
        ):
            if self.invite_own_puppet_to_pm and invite:
                await self.main_intent.invite_user(self.mxid, UserID(sender.mxid))
            elif (
                await self.az.state_store.get_membership(self.mxid, UserID(sender.mxid))
                != Membership.JOIN
            ):
                self.log.warning(
                    f"Ignoring own {mid} in private chat because own puppet is not in"
                    " room."
                )
                return False
        return True

    async def handle_linkedin_message(
        self,
        source: "u.User",
        sender: "p.Puppet",
        message: ConversationEvent,
    ):
        try:
            if message.subtype == "CONVERSATION_UPDATE":
                if (
                    (ec := message.event_content)
                    and (me := ec.message_event)
                    and (cc := me.custom_content)
                    and (nu := cc.conversation_name_update_content)
                ):
                    await self._update_name(nu.new_name)
            elif (
                (ec := message.event_content)
                and (me := ec.message_event)
                and me.recalled_at
            ):
                await self._handle_linkedin_message_deletion(sender, message)
            else:
                await self._handle_linkedin_message(source, sender, message)
        except Exception as e:
            self.log.exception(
                f"Error handling LinkedIn message {message.entity_urn}: {e}"
            )

    async def _handle_linkedin_message(
        self,
        source: "u.User",
        sender: "p.Puppet",
        message: ConversationEvent,
    ):
        assert self.mxid
        assert self.li_receiver_urn
        assert message.entity_urn
        li_message_urn = message.entity_urn

        # Check in-memory queue for duplicates
        message_exists = False
        event_ids: list[EventID] = []
        async with self.require_send_lock(sender.li_member_urn):
            if li_message_urn in self._dedup:
                self.log.trace(
                    f"Not handling message {li_message_urn}, found ID in dedup queue"
                )
                # Return here, because it is in the process of being handled.
                return
            self._dedup.appendleft(li_message_urn)

            # Check database for duplicates
            dbm = await DBMessage.get_all_by_li_message_urn(
                li_message_urn, self.li_receiver_urn
            )
            if len(dbm) > 0:
                self.log.debug(
                    f"Not handling message {li_message_urn}, found duplicate in "
                    "database."
                )
                # Don't return here because we may need to update the reactions.
                message_exists = True
                event_ids = [dbm.mxid for dbm in sorted(dbm, key=lambda m: m.index)]

        intent = sender.intent_for(self)
        if not message_exists:
            self.log.trace("LinkedIn event content: %s", message)
            if not self.mxid:
                mxid = await self.create_matrix_room(source)
                if not mxid:
                    # Failed to create
                    return
            if not await self._bridge_own_message_pm(
                source, sender, f"message {li_message_urn}"
            ):
                return

            if (
                self._backfill_leave is not None
                and self.li_other_user_urn != sender.li_member_urn
                and intent != sender.intent
                and intent not in self._backfill_leave
            ):
                self.log.debug(
                    "Adding %s's default puppet to room for backfilling", sender.mxid
                )
                await self.main_intent.invite_user(self.mxid, intent.mxid)
                await intent.ensure_joined(self.mxid)
                self._backfill_leave.add(intent)

            if (ec := message.event_content) and (message_event := ec.message_event):
                timestamp = message.created_at or datetime.now()

                event_ids = []

                # Handle subject
                if message_event.subject:
                    event_ids.append(
                        await self._send_message(
                            intent,
                            linkedin_subject_to_matrix(message_event.subject),
                            timestamp=timestamp,
                        )
                    )

                # Handle attachments
                event_ids.extend(
                    await self._handle_linkedin_attachments(
                        source, intent, timestamp, message_event.attachments
                    )
                )

                # Handle custom content
                if cc := message_event.custom_content:
                    if cc.third_party_media:
                        event_ids.extend(
                            await self._handle_linkedin_third_party_media(
                                source,
                                intent,
                                timestamp,
                                cc.third_party_media,
                            )
                        )

                    # Handle InMail message text
                    if cc.sp_inmail_content:
                        event_ids.append(
                            await self._send_message(
                                intent,
                                await linkedin_spinmail_to_matrix(cc.sp_inmail_content),
                                timestamp=timestamp,
                            )
                        )

                # Handle the normal message text itself
                if message_event.attributed_body and message_event.attributed_body.text:
                    content = await linkedin_to_matrix(message_event.attributed_body)
                    event_ids.append(
                        await self._send_message(intent, content, timestamp=timestamp)
                    )
                    # TODO (#55) error handling

                event_ids = [event_id for event_id in event_ids if event_id]
                if len(event_ids) == 0:
                    return

                # Save all of the messages in the database.
                self.log.debug(
                    f"Handled LinkedIn message {li_message_urn} -> {event_ids}"
                )
                await DBMessage.bulk_create(
                    li_message_urn=li_message_urn,
                    li_thread_urn=self.li_thread_urn,
                    li_sender_urn=sender.li_member_urn,
                    li_receiver_urn=self.li_receiver_urn,
                    mx_room=self.mxid,
                    timestamp=timestamp,
                    event_ids=event_ids,
                )
                await self._send_delivery_receipt(event_ids[-1])
        # end if message_exists

        # Handle reactions
        reaction_event_id = event_ids[-1]  # react to the last event
        for reaction_summary in message.reaction_summaries:
            await self._handle_reaction_summary(
                li_message_urn,
                source,
                reaction_event_id,
                reaction_summary,
            )

    async def _handle_linkedin_message_deletion(
        self,
        sender: "p.Puppet",
        message: ConversationEvent,
    ):
        if not self.mxid or not self.li_receiver_urn:
            return
        for db_message in await DBMessage.get_all_by_li_message_urn(
            message.entity_urn, self.li_receiver_urn
        ):
            try:
                await sender.intent_for(self).redact(
                    db_message.mx_room,
                    db_message.mxid,
                    timestamp=message.created_at,
                )
            except MForbidden:
                await self.main_intent.redact(
                    db_message.mx_room,
                    db_message.mxid,
                    timestamp=message.created_at,
                )
            await db_message.delete()

    async def _handle_reaction_summary(
        self,
        li_message_urn: URN,
        source: "u.User",
        reaction_event_id: EventID,
        reaction_summary: ReactionSummary,
    ) -> list[EventID]:
        if not reaction_summary.emoji or not source.client:
            return []

        assert self.mxid
        assert self.li_receiver_urn

        emoji = reaction_summary.emoji
        reactors = await source.client.get_reactors(li_message_urn, emoji)

        mxids = []
        for reactor in reactors.elements:
            sender = await p.Puppet.get_by_li_member_urn(reactor.reactor_urn)
            intent = sender.intent_for(self)

            mxid = await intent.react(
                self.mxid, reaction_event_id, reaction_summary.emoji
            )
            mxids.append(mxid)

            self.log.debug(
                f"{sender.mxid} reacted to {reaction_event_id} with "
                f"{reaction_summary.emoji}, got {mxid}."
            )

            await DBReaction(
                mxid=mxid,
                mx_room=self.mxid,
                li_message_urn=li_message_urn,
                li_receiver_urn=self.li_receiver_urn,
                li_sender_urn=sender.li_member_urn,
                reaction=reaction_summary.emoji,
            ).insert()

        return mxids

    async def _handle_linkedin_attachments(
        self,
        source: "u.User",
        intent: IntentAPI,
        timestamp: datetime,
        attachments: list[MessageAttachment],
    ) -> list[EventID]:
        event_ids = []
        for attachment in attachments:
            if not attachment.reference:
                continue
            url = attachment.reference.string
            if not url:
                continue

            msgtype = MessageType.FILE
            if attachment.media_type.startswith("image/"):
                msgtype = MessageType.IMAGE
            else:
                msgtype = MessageType.FILE

            mxc, info, decryption_info = await self._reupload_linkedin_file(
                url, source, intent, encrypt=self.encrypted, find_size=True
            )
            content = MediaMessageEventContent(
                url=mxc,
                file=decryption_info,
                info=info,
                msgtype=msgtype,
                body=attachment.name,
            )

            event_id = await self._send_message(
                intent,
                content,
                timestamp=timestamp,
            )
            # TODO (#55) error handling

            event_ids.append(event_id)

        return event_ids

    async def _handle_linkedin_third_party_media(
        self,
        source: "u.User",
        intent: IntentAPI,
        timestamp: datetime,
        third_party_media: ThirdPartyMedia,
    ) -> list[EventID]:
        if not third_party_media:
            return []

        if third_party_media.media_type == "TENOR_GIF":
            if not third_party_media.media or not third_party_media.media.gif:
                return []
            msgtype = MessageType.IMAGE
            mxc, info, decryption_info = await self._reupload_linkedin_file(
                third_party_media.media.gif.url,
                source,
                intent,
                encrypt=self.encrypted,
                width=third_party_media.media.gif.original_width,
                height=third_party_media.media.gif.original_height,
            )
            content = MediaMessageEventContent(
                url=mxc,
                file=decryption_info,
                info=info,
                msgtype=msgtype,
            )

            event_id = await self._send_message(
                intent,
                content,
                timestamp=timestamp,
            )
            # TODO (#55) error handling
            return [event_id]

        self.log.warning(f"Unsupported third party media: {third_party_media}.")
        return []

    @classmethod
    async def _reupload_linkedin_file(
        cls,
        url: str,
        source: "u.User",
        intent: IntentAPI,
        *,
        filename: Optional[str] = None,
        encrypt: bool = False,
        find_size: bool = False,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> tuple[ContentURI, MediaInfo, Optional[EncryptedFile]]:
        if not url:
            raise ValueError("URL not provided")

        assert source.client

        file_data = await source.client.download_linkedin_media(url)
        if len(file_data) > cls.matrix.media_config.upload_size:
            raise ValueError("File not available: too large")

        mime = magic.from_buffer(file_data, mime=True)

        info = FileInfo(mimetype=mime, size=len(file_data))
        if Image and mime.startswith("image/"):
            if (width is None or height is None) and find_size:
                with Image.open(BytesIO(file_data)) as img:
                    width, height = img.size
            if width and height:
                info = ImageInfo(
                    mimetype=mime,
                    size=len(file_data),
                    width=width,
                    height=height,
                )

        upload_mime_type = mime
        decryption_info = None
        if encrypt and encrypt_attachment:
            file_data, decryption_info = encrypt_attachment(file_data)
            upload_mime_type = "application/octet-stream"
            filename = None
        url = await intent.upload_media(
            file_data, mime_type=upload_mime_type, filename=filename
        )
        if decryption_info:
            decryption_info.url = url
        return url, info, decryption_info

    async def handle_linkedin_reaction_add(
        self,
        source: "u.User",
        sender: "p.Puppet",
        event: RealTimeEventStreamEvent,
    ):
        if (
            not event.event_urn
            or not self.li_receiver_urn
            or not event.reaction_summary
        ):
            return
        reaction = event.reaction_summary.emoji
        # Make up a URN for the reacton for dedup purposes
        dedup_id = URN(
            f"({event.event_urn.id_str()},{sender.li_member_urn.id_str()},{reaction})"
        )
        async with self.optional_send_lock(sender.li_member_urn):
            if dedup_id in self._dedup:
                return
            self._dedup.appendleft(dedup_id)

            # Check database for duplicates
            dbr = await DBReaction.get_by_li_message_urn_and_emoji(
                event.event_urn,
                self.li_receiver_urn,
                sender.li_member_urn,
                reaction,
            )
            if dbr:
                self.log.debug(
                    f"Not handling reaction {reaction} to {event.event_urn}, found "
                    "duplicate in database."
                )
                return

        if not await self._bridge_own_message_pm(
            source, sender, f"reaction to {event.event_urn}"
        ):
            return

        intent = sender.intent_for(self)

        message = await DBMessage.get_by_li_message_urn(
            event.event_urn, self.li_receiver_urn
        )
        if not message:
            self.log.debug(f"Ignoring reaction to unknown message {event.event_urn}")
            return

        mxid = await intent.react(message.mx_room, message.mxid, reaction)
        self.log.debug(f"Reacted to {message.mxid}, got {mxid}")

        await DBReaction(
            mxid=mxid,
            mx_room=message.mx_room,
            li_message_urn=message.li_message_urn,
            li_receiver_urn=self.li_receiver_urn,
            li_sender_urn=sender.li_member_urn,
            reaction=reaction,
        ).insert()
        self._dedup.remove(dedup_id)

    async def handle_linkedin_reaction_remove(
        self,
        source: "u.User",
        sender: "p.Puppet",
        event: RealTimeEventStreamEvent,
    ):
        if (
            not self.mxid
            or not self.li_receiver_urn
            or not event.event_urn
            or not event.reaction_summary
        ):
            return
        reaction = await DBReaction.get_by_li_message_urn_and_emoji(
            event.event_urn,
            self.li_receiver_urn,
            sender.li_member_urn,
            event.reaction_summary.emoji,
        )
        if reaction:
            try:
                await sender.intent_for(self).redact(reaction.mx_room, reaction.mxid)
            except MForbidden:
                await self.main_intent.redact(reaction.mx_room, reaction.mxid)
            await reaction.delete()

    # endregion
