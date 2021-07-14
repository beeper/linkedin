import asyncio
from collections import deque
from datetime import datetime
from io import BytesIO
from typing import (
    Any,
    AsyncGenerator,
    cast,
    Deque,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    TYPE_CHECKING,
    Union,
)

import magic
from linkedin_messaging import URN
from linkedin_messaging.api_objects import (
    AttributedBody,
    Conversation,
    ConversationEvent,
    MessageAttachment,
    MessageCreate,
    ReactionSummary,
    ThirdPartyMedia,
)
from mautrix.appservice import IntentAPI
from mautrix.bridge import async_getter_lock, BasePortal, NotificationDisabler
from mautrix.errors import MatrixError
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

StateBridge = EventType.find("m.bridge", EventType.Class.STATE)
StateHalfShotBridge = EventType.find("uk.half-shot.bridge", EventType.Class.STATE)
MediaInfo = Union[FileInfo, VideoInfo, AudioInfo, ImageInfo]


class Portal(DBPortal, BasePortal):
    invite_own_puppet_to_pm: bool = False
    by_mxid: Dict[RoomID, "Portal"] = {}
    by_li_thread_urn: Dict[Tuple[URN, Optional[URN]], "Portal"] = {}
    matrix: "MatrixHandler"
    config: Config

    backfill_lock: SimpleLock
    _dedup: Deque[URN]
    _send_locks: Dict[URN, asyncio.Lock]

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
        encrypted: bool = False,
    ) -> None:
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
        self._backfill_leave: Optional[Set[IntentAPI]] = None

    @classmethod
    def init_cls(cls, bridge: "LinkedInBridge") -> None:
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

    async def delete(self) -> None:
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

    # endregion

    # region Properties

    @property
    def li_urn_full(self) -> Tuple[URN, Optional[URN]]:
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

    async def postinit(self) -> None:
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
        for portal in cast(List[Portal], portals):
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
    ) -> Conversation:
        if not conversation:
            # shouldn't happen currently
            assert False, "update_info called without conversation"

        if conversation.entity_urn != self.li_thread_urn:
            self.log.warning(
                f"Got different ID ({conversation.entity_urn}) than what was asked "
                f"for ({self.li_thread_urn}) when fetching"
            )

        changed = False

        if not self.is_direct:
            # TODO (#53)
            # changed = any(
            #     await asyncio.gather(
            #         self._update_name(info.name),
            #         self._update_photo(source, info.image),
            #         loop=self.loop,
            #     )
            # )
            pass

        changed = await self._update_participants(source, conversation) or changed
        if changed:
            await self.update_bridge_info()
            await self.save()

        return conversation

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
            participant_urn = participant.messaging_member.mini_profile.entity_urn
            puppet = await p.Puppet.get_by_li_member_urn(participant_urn)
            await puppet.update_info(source, participant.messaging_member)
            if (
                self.is_direct
                and self.li_other_user_urn == puppet.li_member_urn
                and self.encrypted
            ):
                pass
                # TODO (#53)
                # changed = await self._update_name(puppet.name) or changed
                # changed = await self._update_photo_from_puppet(puppet) or changed

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

        info = await self.update_info(source, conversation)
        # if not info:
        #     self.log.debug(
        #         "update_info() didn't return info, cancelling room creation")
        #     return None

        # if self.encrypted or not self.is_direct:
        #     name = self.name
        #     initial_state.append(
        #         {
        #             "type": str(EventType.ROOM_AVATAR),
        #             "content": {"avatar_url": self.avatar_url},
        #         }
        #     )

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
                await self._update_participants(source, info)
            else:
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
    def bridge_info(self) -> Dict[str, Any]:
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
        after_timestamp: Optional[datetime],  # TODO (54)
        conversation: Conversation,
    ):
        assert self.mxid
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

            before_timestamp = messages[0].created_at

        self._backfill_leave = set()
        async with NotificationDisabler(self.mxid, source):
            for message in messages:
                member_urn = message.from_.messaging_member.mini_profile.entity_urn
                puppet = await p.Puppet.get_by_li_member_urn(member_urn)
                await self.handle_linkedin_message(source, puppet, message)
        for intent in self._backfill_leave:
            self.log.trace(f"Leaving room with {intent.mxid} post-backfill")
            await intent.leave_room(self.mxid)
        self.log.info(f"Backfilled {len(messages)} messages through {source.mxid}")

    # endregion

    # region Matrix event handling

    async def handle_matrix_message(
        self,
        sender: "u.User",
        message: MessageEventContent,
        event_id: EventID,
    ):
        try:
            await self._handle_matrix_message(sender, message, event_id)
        except Exception:
            self.log.exception(f"Failed handling {event_id}")

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
        elif message.msgtype in (
            MessageType.AUDIO,
            MessageType.FILE,
            MessageType.IMAGE,
            MessageType.VIDEO,
        ):
            await self._handle_matrix_media(
                event_id,
                sender,
                cast(MediaMessageEventContent, message),
            )
        else:
            self.log.warning(f"Unsupported msgtype {message.msgtype} in {event_id}")
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
        await self._send_linkedin_message(
            event_id,
            sender,
            MessageCreate(AttributedBody(), attachments=[attachment]),
        )

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
        li_message_urn = message.entity_urn

        # Check in-memory queue for duplicates
        async with self.require_send_lock(sender.li_member_urn):
            if li_message_urn in self._dedup:
                self.log.trace(
                    f"Not handling message {li_message_urn}, found ID in dedup queue"
                )
                return
            self._dedup.appendleft(li_message_urn)

            # Check database for duplicates
            dbm = await DBMessage.get_by_li_message_urn(
                li_message_urn, self.li_receiver_urn
            )
            if dbm:
                self.log.debug(
                    f"Not handling message {li_message_urn}, found duplicate in "
                    "database."
                )
                return

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

        intent = sender.intent_for(self)

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

        message_event = message.event_content.message_event
        timestamp = message.created_at

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
        if message_event.custom_content:
            if message_event.custom_content.third_party_media:
                event_ids.extend(
                    await self._handle_linkedin_third_party_media(
                        source,
                        intent,
                        timestamp,
                        message_event.custom_content.third_party_media,
                    )
                )

            # Handle InMail message text
            if message_event.custom_content.sp_inmail_content:
                event_ids.append(
                    await self._send_message(
                        intent,
                        await linkedin_spinmail_to_matrix(
                            message_event.custom_content.sp_inmail_content
                        ),
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
        self.log.debug(f"Handled LinkedIn message {li_message_urn} -> {event_ids}")
        await DBMessage.bulk_create(
            li_message_urn=li_message_urn,
            li_thread_urn=self.li_thread_urn,
            li_sender_urn=sender.li_member_urn,
            li_receiver_urn=self.li_receiver_urn,
            mx_room=self.mxid,
            timestamp=timestamp,
            event_ids=event_ids,
        )
        # TODO (#48)
        # await self._send_delivery_receipt(event_ids[-1])

        # Handle reactions
        reaction_summaries = sorted(
            message.reaction_summaries,
            key=lambda r: r.first_reacted_at,
            reverse=True,
        )
        reaction_event_id = event_ids[-1]  # react to the last event
        for reaction_summary in reaction_summaries:
            await self.handle_reaction_summary(
                intent,
                li_message_urn,
                sender,
                reaction_event_id,
                reaction_summary,
            )

    async def handle_reaction_summary(
        self,
        intent: IntentAPI,
        li_message_urn: URN,
        sender: "p.Puppet",
        reaction_event_id: EventID,
        reaction_summary: ReactionSummary,
    ) -> Optional[EventID]:
        if not reaction_summary.emoji:
            return None

        assert self.mxid
        assert self.li_receiver_urn

        # TODO (#32) figure out how many reactions should be added
        mxid = await intent.react(self.mxid, reaction_event_id, reaction_summary.emoji)
        self.log.debug(
            f"Reacted to {reaction_event_id} with {reaction_summary.emoji}, got {mxid}"
        )
        await DBReaction(
            mxid=mxid,
            mx_room=self.mxid,
            li_message_urn=li_message_urn,
            li_receiver_urn=self.li_receiver_urn,
            li_sender_urn=sender.li_member_urn,
            reaction=reaction_summary.emoji,
        ).insert()
        return mxid

    async def _handle_linkedin_attachments(
        self,
        source: "u.User",
        intent: IntentAPI,
        timestamp: datetime,
        attachments: List[MessageAttachment],
    ) -> List[EventID]:
        event_ids = []
        for attachment in attachments:
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
    ) -> List[EventID]:
        if not third_party_media:
            return []

        if third_party_media.media_type == "TENOR_GIF":
            if third_party_media.media.gif.url:
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
    ) -> Tuple[ContentURI, MediaInfo, Optional[EncryptedFile]]:
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

    # endregion
