import asyncio
from collections import deque
from datetime import datetime
from html import escape
from io import BytesIO
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
from urllib import parse

import aiohttp
import magic
import requests
from bs4 import BeautifulSoup
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
from yarl import URL

from .config import Config
from .db import (
    Portal as DBPortal,
    Message as DBMessage,
    Reaction as DBReaction,
    UserPortal,
)
from .formatter import linkedin_to_matrix, matrix_to_linkedin
from . import puppet as p, user as u

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
    decrypt_attachment = encrypt_attachment = None

StateBridge = EventType.find("m.bridge", EventType.Class.STATE)
StateHalfShotBridge = EventType.find("uk.half-shot.bridge", EventType.Class.STATE)
MediaInfo = Union[FileInfo, VideoInfo, AudioInfo, ImageInfo]


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
        return not self.li_is_group_chat

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

        if (
            cast(str, conversation.get("entityUrn")).split(":")[-1]
            != self.li_thread_urn
        ):
            self.log.warning(
                "Got different ID (%s) than what was asked for (%s) when fetching",
                conversation.get("entityUrn"),
                self.li_thread_urn,
            )

        # TODO actually update things
        changed = False

        if not self.is_direct:
            # print("not direct", conversation)
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
        nick_map = {}  # TODO can we support this?
        for participant in participants:
            # TODO turn Participant into an actual class and deserialize it.
            # For now, this will have to suffice
            participant = participant.get(
                "com.linkedin.voyager.messaging.MessagingMember", {}
            )
            participant_urn = (
                participant.get("miniProfile", {}).get("entityUrn", "").split(":")[-1]
            )

            puppet = await p.Puppet.get_by_li_member_urn(participant_urn)
            await puppet.update_info(source, participant)
            if (
                self.is_direct
                and self.li_other_user_urn == puppet.li_member_urn
                and self.encrypted
            ):
                pass
                # TODO
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
        assert self.mxid
        self.log.debug("Backfilling history through %s", source.mxid)
        messages = conversation.get("events", [])

        # TODO do whatever needs to be done to prevent it from backfilling if there are
        # no new messages
        return

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

        self._backfill_leave = set()
        async with NotificationDisabler(self.mxid, source):
            for message in messages:
                member_urn = (
                    message.get("from", {})
                    .get("com.linkedin.voyager.messaging.MessagingMember", {})
                    .get("miniProfile", {})
                    .get("entityUrn", "")
                    .split(":")[-1]
                )
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
            await self._handle_matrix_text(event_id, sender, message)
        elif message.msgtype == MessageType.AUDIO:
            print("audio", message)
        elif message.msgtype == MessageType.FILE:
            print("file", message)
        elif message.msgtype == MessageType.IMAGE:
            await self._handle_matrix_image(event_id, sender, message)
        elif message.msgtype == MessageType.VIDEO:
            print("video", message)
        elif message.msgtype == MessageType.LOCATION:
            print("location", message)
        elif message.msgtype == MessageType.STICKER:
            print("sticker", message)
        else:
            self.log.warning(f"Unsupported msgtype {message.msgtype} in {event_id}")
            return

    async def _handle_matrix_text(
        self,
        event_id: EventID,
        sender: "u.User",
        message: TextMessageEventContent,
    ):
        converted = await matrix_to_linkedin(
            message, sender, self.main_intent, self.log
        )
        conversation_urn = self.li_thread_urn.split(":")[-1]
        failure = sender.linkedin_client.send_message(
            converted.text,
            conversation_urn,
            attributes=[m.to_json() for m in converted.mentions],
        )
        if failure:
            raise Exception(f"Send message to {conversation_urn} failed")

    async def _handle_matrix_image(
        self,
        event_id: EventID,
        sender: "u.User",
        message: MediaMessageEventContent,
    ):
        upload_metadata_response = sender.linkedin_client._post(
            "/voyagerMediaUploadMetadata",
            params={"action": "upload"},
            json={
                "mediaUploadType": "MESSAGING_PHOTO_ATTACHMENT",
                "fileSize": message.info.size,
                "filename": message.body,
            },
        )
        if upload_metadata_response.status_code != 200:
            self.main_intent.send_notice(self.mxid, "Failed to send upload metadata")
        upload_metadata_response_json = upload_metadata_response.json().get("value", {})
        print(upload_metadata_response_json)
        upload_url = upload_metadata_response_json.get("singleUploadUrl")
        assert upload_url

        if message.file and decrypt_attachment:
            data = await self.main_intent.download_media(message.file.url)
            data = decrypt_attachment(
                data,
                message.file.key.key,
                message.file.hashes.get("sha256"),
                message.file.iv,
            )
        elif message.url:
            data = await self.main_intent.download_media(message.url)
        else:
            return

        upload_response = sender.linkedin_client.client.session.put(
            upload_url, data=data
        )
        if upload_response.status_code != 201:
            self.main_intent.send_notice(self.mxid, "Failed to upload file")

        conversation_urn = self.li_thread_urn.split(":")[-1]
        failure = sender.linkedin_client.send_message(
            "",
            conversation_urn,
            attachments=[
                {
                    "id": upload_metadata_response_json.get("urn"),
                    "name": message.body,
                    "byteSize": message.info.size,
                    "mediaType": message.info.mimetype,
                }
            ],
        )
        if failure:
            raise Exception(f"Send message to {conversation_urn} failed")

    # endregion

    # region LinkedIn event handling

    async def _bridge_own_message_pm(
        self,
        source: "u.User",
        sender: "p.Puppet",
        mid: str,
        invite: bool = True,
    ) -> bool:
        if (
            self.is_direct
            and sender.li_member_urn == source.li_member_urn
            and not sender.is_real_user
        ):
            if self.invite_own_puppet_to_pm and invite:
                await self.main_intent.invite_user(self.mxid, sender.mxid)
            elif (
                await self.az.state_store.get_membership(self.mxid, sender.mxid)
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
        message: Dict[str, Any],
    ):
        try:
            await self._handle_linkedin_message(source, sender, message)
        except Exception:
            self.log.exception(
                f"Error handling LinkedIn message {message.get('entityUrn')}",
            )

    async def _handle_linkedin_message(
        self,
        source: "u.User",
        sender: "p.Puppet",
        message: Dict[str, Any],
    ):
        assert self.mxid
        assert self.li_receiver_urn

        li_message_urn = message.get("entityUrn")
        if li_message_urn is None:
            self.log.exception("entityUrn was None")
            return

        # Check in-memory queue for duplicates
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
                f"Not handling message {li_message_urn}, found duplicate in database"
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

        message_event = message.get("eventContent", {}).get(
            "com.linkedin.voyager.messaging.event.MessageEvent", {}
        )
        timestamp = message.get("createdAt", int(datetime.now().timestamp() * 1000))

        if message_event is None:
            self.log.exception(f"No message event found in message {li_message_urn}")
            return

        event_ids = await self._handle_attachments(
            source,
            intent,
            timestamp,
            message_event.get("attachments", []),
        ) + await self._handle_third_party_media(
            source,
            intent,
            timestamp,
            message_event.get("customContent", {}).get(
                "com.linkedin.voyager.messaging.shared.ThirdPartyMedia"
            ),
        )

        # Handle the message text itself
        message_attributed_body = message_event.get("attributedBody", {})
        if message_attributed_body:
            content = await linkedin_to_matrix(message_attributed_body)
            event_ids.append(
                await self._send_message(intent, content, timestamp=timestamp)
            )
            # TODO error handling

        if len(event_ids) == 0:
            return

        # Save all of the messages in the database.
        event_ids = [event_id for event_id in event_ids if event_id]
        self.log.debug(f"Handled Messenger message {li_message_urn} -> {event_ids}")
        await DBMessage.bulk_create(
            li_message_urn=li_message_urn,
            li_thread_urn=self.li_thread_urn,
            li_sender_urn=sender.li_member_urn,
            li_receiver_urn=self.li_receiver_urn,
            mx_room=self.mxid,
            timestamp=timestamp,
            event_ids=event_ids,
        )
        # TODO
        # await self._send_delivery_receipt(event_ids[-1])

        # Handle reactions
        reaction_summaries = sorted(
            message.get("reactionSummaries", []),
            key=lambda m: m.get("firstReactedAt"),
            reverse=True,
        )
        reaction_event_id = event_ids[-1]  # react to the last event
        for reaction_summary in reaction_summaries:
            self.handle_reaction_summary(
                intent,
                li_message_urn,
                sender,
                reaction_event_id,
                reaction_summary,
            )

    async def handle_reaction_summary(
        self,
        intent: IntentAPI,
        li_message_urn: str,
        sender: "p.Puppet",
        reaction_event_id: EventID,
        reaction_summary: Dict[str, Any],
    ) -> Optional[EventID]:
        reaction = reaction_summary.get("emoji")
        if not reaction:
            return None

        assert self.mxid
        assert self.li_receiver_urn

        # TODO figure out how many reactions should be added
        mxid = await intent.react(self.mxid, reaction_event_id, reaction)
        self.log.debug(f"Reacted to {reaction_event_id}, got {mxid}")
        await DBReaction(
            mxid=mxid,
            mx_room=self.mxid,
            li_message_urn=li_message_urn,
            li_receiver_urn=self.li_receiver_urn,
            li_sender_urn=sender.li_member_urn,
            reaction=reaction,
        ).insert()
        return mxid

    async def _handle_attachments(
        self,
        source: "u.User",
        intent: IntentAPI,
        timestamp: Optional[int],
        attachments: List[Dict[str, Any]],
    ) -> List[EventID]:
        event_ids = []
        for attachment in attachments:
            media_type = attachment.get("mediaType", "")

            msgtype = MessageType.FILE
            if media_type.startswith("image/"):
                msgtype = MessageType.IMAGE
            else:
                msgtype = MessageType.FILE

            url = attachment.get("reference", {}).get("string")
            if not url:
                continue

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
            # TODO error handling

            event_ids.append(event_id)

        return event_ids

    async def _handle_third_party_media(
        self,
        source: "u.User",
        intent: IntentAPI,
        timestamp: Optional[int],
        third_party_media: Dict[str, Any],
    ) -> List[EventID]:
        if not third_party_media:
            return []

        if third_party_media.get("mediaType") == "TENOR_GIF":
            gif_url = third_party_media.get("media", {}).get("gif", {}).get("url")
            if gif_url:
                msgtype = MessageType.IMAGE
                # TODO get the width and height from the JSON response
                mxc, info, decryption_info = await self._reupload_linkedin_file(
                    gif_url, source, intent, encrypt=self.encrypted, find_size=True
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
                # TODO error handling
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
    ) -> Tuple[ContentURI, MediaInfo, Optional[EncryptedFile]]:
        if not url:
            raise ValueError("URL not provided")
        # TODO move this to the linkedin-api
        file_data = requests.get(url, cookies=source.linkedin_client.client.cookies)
        if not file_data.ok:
            raise Exception("Couldn't download media")

        if len(file_data.content) > cls.matrix.media_config.upload_size:
            raise ValueError("File not available: too large")

        data = file_data.content
        mime = magic.from_buffer(data, mime=True)

        info = FileInfo(mimetype=mime, size=len(data))
        if Image and mime.startswith("image/") and find_size:
            with Image.open(BytesIO(data)) as img:
                width, height = img.size
            info = ImageInfo(mimetype=mime, size=len(data), width=width, height=height)

        upload_mime_type = mime
        decryption_info = None
        if encrypt and encrypt_attachment:
            data, decryption_info = encrypt_attachment(data)
            upload_mime_type = "application/octet-stream"
            filename = None
        url = await intent.upload_media(
            data, mime_type=upload_mime_type, filename=filename
        )
        if decryption_info:
            decryption_info.url = url
        return url, info, decryption_info

    # endregion
