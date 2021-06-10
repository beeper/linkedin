import asyncio
from collections import deque
from datetime import datetime
from typing import (
    Dict,
    Deque,
    Optional,
    Tuple,
    Union,
    Set,
    AsyncGenerator,
    List,
    Any,
    Awaitable,
    Pattern,
    TYPE_CHECKING,
    cast,
)

from mautrix.appservice import IntentAPI
from mautrix.bridge import async_getter_lock, BasePortal, NotificationDisabler
from mautrix.errors import (
    MForbidden,
    MNotFound,
    IntentError,
    MatrixError,
    SessionNotFound,
)
from mautrix.types import (
    RoomID,
    EventType,
    ContentURI,
    MessageEventContent,
    EventID,
    ImageInfo,
    MessageType,
    LocationMessageEventContent,
    FileInfo,
    AudioInfo,
    Format,
    RelationType,
    TextMessageEventContent,
    MediaMessageEventContent,
    Membership,
    EncryptedFile,
    VideoInfo,
    MemberStateEventContent,
)
from mautrix.util.simple_lock import SimpleLock

from .config import Config
from .db import (
    Portal as DBPortal,
    Message as DBMessage,
    Reaction as DBReaction,
    UserPortal,
)
from . import puppet as p, user as u

if TYPE_CHECKING:
    from .__main__ import LinkedInBridge
    from .matrix import MatrixHandler

StateBridge = EventType.find("m.bridge", EventType.Class.STATE)
StateHalfShotBridge = EventType.find("uk.half-shot.bridge", EventType.Class.STATE)


class Portal(DBPortal, BasePortal):
    invite_own_puppet_to_pm: bool = False
    by_mxid: Dict[RoomID, "Portal"] = {}
    by_li_thread_urn: Dict[Tuple[str, str], "Portal"] = {}
    matrix: "MatrixHandler"
    config: Config

    backfill_lock: SimpleLock

    def __init__(
        self,
        li_thread_urn: str,
        li_receiver_urn: str,
        li_is_group_chat: bool,
        li_other_user_urn: Optional[str] = None,
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
        self._oti_dedup = {}
        self._send_locks = {}
        self._typing = set()

        self.backfill_lock = SimpleLock(
            "Waiting for backfilling to finish before handling %s", log=self.log
        )
        self._backfill_leave = None

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

    # region Properties

    @property
    def li_urn_full(self) -> Tuple[str, str]:
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
        # TODO
        return True

    # endregion

    # region Properties

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
        li_thread_urn: str,
        *,
        li_receiver_urn: str = None,
        li_is_group_chat: bool = False,
        li_other_user_urn: str = None,
        create: bool = True,
    ) -> Optional["Portal"]:
        try:
            return cls.by_li_thread_urn[(li_thread_urn, li_receiver_urn)]
        except KeyError:
            pass

        portal = cast(
            Portal,
            await super().get_by_li_thread_urn(
                li_thread_urn,
                li_receiver_urn,
            ),
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
        conversation: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        if not conversation:
            # shouldn't happen currently
            assert False, "update_info called without conversation"

        if conversation.get("entityUrn") != self.li_thread_urn:
            self.log.warning(
                "Got different ID (%s) than what was asked for (%s) when fetching",
                conversation.get("entityUrn"),
                self.li_thread_urn,
            )

        # TODO actually update things
        changed = False

        if not self.is_direct:
            pass
            # TODO
            # changed = any(
            #     await asyncio.gather(
            #         self._update_name(info.name),
            #         self._update_photo(source, info.image),
            #         loop=self.loop,
            #     )
            # )

        changed = await self._update_participants(source, conversation) or changed
        if changed:
            # TODO
            # await self.update_bridge_info()
            await self.save()

        return conversation

    async def _update_participants(
        self,
        source: "u.User",
        conversation: Dict[str, Any],
    ) -> bool:
        changed = False

        participants = conversation.get("participants", [])
        nick_map = {}
        for participant in participants:
            # TODO turn Participant into an actual class and deserialize it.
            # For now, this will have to suffice
            participant = participant.get(
                "com.linkedin.voyager.messaging.MessagingMember", {}
            )
            participant_urn = (
                participant.get("miniProfile", {}).get("objectUrn", "").split(":")[-1]
            )

            puppet = await p.Puppet.get_by_li_member_urn(participant_urn)
            await puppet.update_info(source, participant)

        return changed
        nick_map = (
            info.customization_info.nickname_map if info.customization_info else {}
        )
        for participant in info.all_participants.nodes:
            puppet = await p.Puppet.get_by_fbid(int(participant.id))
            await puppet.update_info(source, participant.messaging_actor)
            if self.is_direct and self.fbid == puppet.fbid and self.encrypted:
                changed = await self._update_name(puppet.name) or changed
                changed = await self._update_photo_from_puppet(puppet) or changed
            if self.mxid:
                if puppet.fbid != self.fb_receiver or puppet.is_real_user:
                    await puppet.intent_for(self).ensure_joined(
                        self.mxid, bot=self.main_intent
                    )
                if puppet.fbid in nick_map:
                    await self.sync_per_room_nick(puppet, nick_map[puppet.fbid])
        return changed

    # endregion

    # region Matrix room creation

    async def create_matrix_room(
        self,
        source: "u.User",
        conversation: Optional[Dict[str, Any]] = None,
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
        conversation: Optional[Dict[str, Any]] = None,
    ):
        try:
            await self._update_matrix_room(source, conversation)
        except Exception:
            self.log.exception("Failed to update portal")

    async def _create_matrix_room(
        self,
        source: "u.User",
        conversation: Optional[Dict[str, Any]] = None,
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
                # TODO remove this once https://github.com/matrix-org/matrix-doc/pull/2346 is in spec
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
        #     self.log.debug("update_info() didn't return info, cancelling room creation")
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
                await self.backfill(source, is_initial=True, conversation=conversation)
            except Exception:
                self.log.exception("Failed to backfill new portal")

            # await self._sync_read_receipts(info.read_receipts.nodes)

        return self.mxid

    async def _update_matrix_room(
        self,
        source: "u.User",
        conversation: Optional[Dict[str, Any]] = None,
    ):
        await self.main_intent.invite_user(self.mxid, source.mxid, check_cache=False)
        puppet = await p.Puppet.get_by_custom_mxid(source.mxid)
        if puppet and puppet.is_real_user:
            await puppet.intent.ensure_joined(self.mxid)
        await self.update_info(source, conversation)

    @property
    def bridge_info_state_key(self) -> str:
        return f"com.github.linkedin://linkedin/{self.li_thread_urn}"

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
                "id": self.li_thread_urn,
                "displayname": self.name,
                "avatar_url": self.avatar_url,
            },
        }

    # endregion

    # region Event backfill

    async def backfill(
        self,
        source: "u.User",
        is_initial: bool,
        conversation: Optional[Dict[str, Any]] = None,
    ):
        limit = (
            self.config["bridge.backfill.initial_limit"]
            if is_initial
            else self.config["bridge.backfill.missed_limit"]
        )
        if limit == 0:
            return
        elif limit < 0:
            limit = None
        last_active = None

        if not is_initial and conversation and len(conversation.get("events", [])) > 0:
            last_active = conversation["events"][-1].get("lastActivityAt")

        most_recent = await DBMessage.get_most_recent(
            self.li_thread_urn, self.li_receiver_urn
        )
        if most_recent and is_initial:
            self.log.debug(
                "Not backfilling %s: already bridged messages found", self.li_urn_log
            )
        elif (not most_recent or not most_recent.timestamp) and not is_initial:
            self.log.debug(
                "Not backfilling %s: no most recent message found", self.li_urn_log
            )
        elif last_active and most_recent and most_recent.timestamp >= last_active:
            self.log.debug(
                "Not backfilling %s: last activity is equal to most recent bridged "
                "message (%s >= %s)",
                self.li_urn_log,
                most_recent.timestamp,
                last_active,
            )
        else:
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
        limit: int,
        after_timestamp: Optional[int],
        conversation: Dict[str, Any],
    ):
        self.log.debug("Backfilling history through %s", source.mxid)
        messages = conversation.get("events", [])

        if len(messages):
            oldest_message = messages[0]
            before_timestamp = datetime.fromtimestamp(
                (oldest_message.get("createdAt") // 1000) - 1
            )
        else:
            before_timestamp = datetime.now()

        self.log.debug(
            "Fetching up to %d messages through %s",
            limit,
            source.li_member_urn,
        )

        conversation_urn = conversation.get("entityUrn", "").split(":")[-1]

        while len(messages) < limit:
            result = source.linkedin_client.get_conversation(
                conversation_urn,
                created_before=before_timestamp,
            )
            elements = result.get("elements", [])

            messages = elements + messages

            if len(elements) < 20:
                break

            oldest_message = messages[0]
            before_timestamp = datetime.fromtimestamp(
                (oldest_message.get("createdAt") / 1000) - 1
            )

        async with NotificationDisabler(self.mxid, source):
            for message in messages:
                member_urn = (
                    message.get("from", {})
                    .get("com.linkedin.voyager.messaging.MessagingMember", {})
                    .get("miniProfile", {})
                    .get("objectUrn", "")
                    .split(":")[-1]
                )
                puppet = await p.Puppet.get_by_li_member_urn(member_urn)
                await self.handle_linkedin_message(source, puppet, message)

    # endregion

    # region Matrix event handling

    async def handle_matrix_message(
        self,
        sender: "u.User",
        message: MessageEventContent,
        event_id: EventID,
    ):
        print("Portal.handle_matrix_message", sender, message, event_id)
        pass

    # endregion

    # region LinkedIn messages

    async def handle_linkedin_message(
        self,
        source: "u.User",
        sender: "p.Puppet",
        message: Dict[str, Any],
    ):
        try:
            await self._handle_linkedin_message(source, sender, message)
        except Exception:
            self.log.exception(
                "Error handling LinkedIn message %s",
                message.get("entityUrn"),
            )

    async def _handle_linkedin_message(
        self,
        source: "u.User",
        sender: "p.Puppet",
        message: Dict[str, Any],
    ):
        assert self.mxid
        self.log.trace("LinkedIn event content: %s", message)
        intent = sender.intent_for(self)

        message_text = (
            message.get("eventContent", {})
            .get("com.linkedin.voyager.messaging.event.MessageEvent", {})
            .get("attributedBody", {})
            .get("text")
        )

        event_type = EventType.ROOM_MESSAGE
        if self.encrypted and self.matrix.e2ee:
            pass
            # if intent.api.is_real_user:
            #     content[intent.api.real_user_content_key] = True
            # event_type, content = await self.matrix.e2ee.encrypt(
            #     self.mxid, event_type, content
            # )

        content = TextMessageEventContent(msgtype=MessageType.TEXT, body=message_text)
        return await intent.send_message_event(self.mxid, event_type, content)

    # endregion
