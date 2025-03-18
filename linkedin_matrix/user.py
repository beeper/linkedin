from __future__ import annotations

from typing import TYPE_CHECKING, AsyncGenerator, AsyncIterable, Awaitable, Optional, cast
from asyncio.futures import Future
from datetime import datetime
import asyncio
import sys
import time

from aiohttp.client_exceptions import ServerConnectionError, TooManyRedirects

from linkedin_messaging import URN, LinkedInMessaging
from linkedin_messaging.api_objects import (
    Conversation,
    ConversationEvent,
    ReactionSummary,
    RealTimeEventStreamEvent,
    UserProfileResponse,
)
from mautrix.bridge import BaseUser, async_getter_lock
from mautrix.errors import MNotFound
from mautrix.types import EventType, PushActionType, PushRuleKind, PushRuleScope, RoomID, UserID
from mautrix.util.bridge_state import BridgeState, BridgeStateEvent
from mautrix.util.opt_prometheus import Gauge, Summary, async_time
from mautrix.util.simple_lock import SimpleLock

from . import portal as po, puppet as pu
from .config import Config
from .db import Cookie, HttpHeader, User as DBUser

if TYPE_CHECKING:
    from .__main__ import LinkedInBridge

METRIC_CONNECTED = Gauge("bridge_connected", "Bridge users connected to LinkedIn")
METRIC_LOGGED_IN = Gauge("bridge_logged_in", "Users logged into the bridge")
METRIC_SYNC_THREADS = Summary("bridge_sync_threads", "calls to sync_threads")


class User(DBUser, BaseUser):
    shutdown: bool = False
    config: Config

    user_profile_cache: UserProfileResponse | None = None

    by_mxid: dict[UserID, "User"] = {}
    by_li_member_urn: dict[URN, "User"] = {}

    listen_task: asyncio.Task | None

    _is_connected: bool | None
    _is_logged_in: bool | None
    _is_logging_out: bool | None
    _is_refreshing: bool
    _notice_room_lock: asyncio.Lock
    _notice_send_lock: asyncio.Lock
    _sync_lock: SimpleLock
    is_admin: bool

    client: LinkedInMessaging | None = None

    def __init__(
        self,
        mxid: UserID,
        li_member_urn: URN | None = None,
        notice_room: RoomID | None = None,
        space_mxid: RoomID | None = None,
    ):
        super().__init__(mxid, li_member_urn, notice_room, space_mxid)
        BaseUser.__init__(self)
        self._notice_room_lock = asyncio.Lock()
        self._notice_send_lock = asyncio.Lock()

        self.command_status = None
        (
            self.is_whitelisted,
            self.is_admin,
            self.permission_level,
        ) = self.config.get_permissions(mxid)
        self._is_logged_in = None
        self._is_logging_out = None
        self._is_connected = None
        self._connection_time = time.monotonic()
        self._prev_thread_sync = -10
        self._prev_reconnect_fail_refresh = time.monotonic()
        self._community_id = None
        self._sync_lock = SimpleLock(
            "Waiting for thread sync to finish before handling %s", log=self.log
        )
        self._is_refreshing = False

        self.log = self.log.getChild(self.mxid)

        self.listen_task = None

    @classmethod
    def init_cls(cls, bridge: LinkedInBridge) -> AsyncIterable[Awaitable[bool]]:
        cls.bridge = bridge
        cls.config = bridge.config
        cls.az = bridge.az
        cls.loop = bridge.loop
        cls.temp_disconnect_notices = bridge.config["bridge.temporary_disconnect_notices"]
        return (user.load_session(is_startup=True) async for user in cls.all_logged_in())

    @property
    def is_connected(self) -> bool | None:
        return self._is_connected

    @is_connected.setter
    def is_connected(self, val: bool | None):
        if self._is_connected != val:
            self._is_connected = val
            self._connection_time = time.monotonic()

    # region Database getters

    def _add_to_cache(self):
        self.by_mxid[self.mxid] = self
        if self.li_member_urn:
            self.by_li_member_urn[self.li_member_urn] = self

    @classmethod
    async def all_logged_in(cls) -> AsyncGenerator["User", None]:
        users = await super().all_logged_in()
        for user in cast(list["User"], users):
            try:
                yield cls.by_mxid[user.mxid]
            except KeyError:
                user._add_to_cache()
                yield user

    @classmethod
    @async_getter_lock
    async def get_by_mxid(
        cls,
        mxid: UserID,
        *,
        create: bool = True,
    ) -> User | None:
        if pu.Puppet.get_id_from_mxid(mxid) or mxid == cls.az.bot_mxid:
            return None
        try:
            return cls.by_mxid[mxid]
        except KeyError:
            pass

        user = cast("User", await super().get_by_mxid(mxid))
        if user is not None:
            user._add_to_cache()
            return user

        if create:
            cls.log.debug(f"Creating user instance for {mxid}")
            user = cls(mxid)
            await user.insert()
            user._add_to_cache()
            return user

        return None

    @classmethod
    @async_getter_lock
    async def get_by_li_member_urn(cls, li_member_urn: URN) -> User | None:
        try:
            return cls.by_li_member_urn[li_member_urn]
        except KeyError:
            pass

        user = cast("User", await super().get_by_li_member_urn(li_member_urn))
        if user is not None:
            user._add_to_cache()
            return user

        return None

    async def get_puppet(self) -> pu.Puppet | None:
        if not self.li_member_urn:
            return None
        return await pu.Puppet.get_by_li_member_urn(self.li_member_urn)

    async def get_portal_with(self, puppet: pu.Puppet, create: bool = True) -> po.Portal | None:
        # We should probably make this work eventually, but for now, creating chats will just not
        # work.
        return None

    # endregion

    # region Session Management

    async def load_session(self, is_startup: bool = False) -> bool:
        if self._is_logged_in and is_startup:
            return True
        cookies = await Cookie.get_for_mxid(self.mxid)
        cookie_names = set(c.name for c in cookies)
        if "li_at" not in cookie_names or "JSESSIONID" not in cookie_names:
            await self.push_bridge_state(BridgeStateEvent.BAD_CREDENTIALS, error="logged-out")
            return False

        self.client = LinkedInMessaging.from_cookies_and_headers(
            {c.name: c.value for c in cookies},
            {h.name: h.value for h in await HttpHeader.get_for_mxid(self.mxid)},
        )

        backoff = 1.0
        while True:
            try:
                self.user_profile_cache = await self.client.get_user_profile()
                break
            except (TooManyRedirects, ServerConnectionError) as e:
                self.log.info(f"Failed to get user profile: {e}")
                await self.push_bridge_state(BridgeStateEvent.BAD_CREDENTIALS, message=str(e))
                return False
            except Exception as e:
                self.log.exception("Failed to get user profile")
                time.sleep(backoff)
                backoff *= 2
                if backoff > 64:
                    # If we can't get the user profile and it's not due to the session being
                    # invalid, it's probably a network error. Go ahead and push the UNKNOWN_ERROR,
                    # and then crash the bridge.
                    await self.push_bridge_state(BridgeStateEvent.UNKNOWN_ERROR, message=str(e))
                    sys.exit(1)

        if (mp := self.user_profile_cache.mini_profile) and mp.entity_urn:
            self.li_member_urn = mp.entity_urn
        else:
            return False

        await self.push_bridge_state(BridgeStateEvent.CONNECTING)

        self.log.info("Loaded session successfully")
        self._track_metric(METRIC_LOGGED_IN, True)
        self._is_logged_in = True
        self.is_connected = None
        self.stop_listen()
        asyncio.create_task(self.post_login())
        return True

    async def reconnect(self):
        assert self.listen_task
        self._is_refreshing = True
        await self.listen_task
        self.listen_task = None
        self.start_listen()
        self._is_refreshing = False

    async def is_logged_in(self) -> bool:
        self.log.debug("Checking if logged in")
        if not self.client:
            self.log.debug("Not logged in: no client")
            return False
        if self._is_logged_in is None:
            try:
                self._is_logged_in = await self.client.logged_in()
                self.log.debug("checked if client is logged in: %s", self._is_logged_in)
            except Exception:
                self.log.exception("Exception checking login status")
                self._is_logged_in = False
                self.user_profile_cache = None
        return self._is_logged_in or False

    async def on_logged_in(self, cookies: dict[str, str], headers: Optional[dict[str, str]]):
        cookies = {k: v.strip('"') for k, v in cookies.items()}
        await Cookie.bulk_upsert(self.mxid, cookies)
        if headers:
            await HttpHeader.bulk_upsert(self.mxid, headers)
        self.client = LinkedInMessaging.from_cookies_and_headers(cookies, headers)
        self.listener_event_handlers_created = False
        self.user_profile_cache = await self.client.get_user_profile()
        if (mp := self.user_profile_cache.mini_profile) and mp.entity_urn:
            self.li_member_urn = mp.entity_urn
        else:
            raise Exception("No mini_profile.entity_urn on the user profile!")
        await self.push_bridge_state(BridgeStateEvent.CONNECTING)
        await self.save()
        self.stop_listen()
        await self.load_session()

    async def post_login(self):
        self.log.info("Running post-login actions")
        self._add_to_cache()

        try:
            puppet = await pu.Puppet.get_by_li_member_urn(self.li_member_urn)

            if puppet.custom_mxid != self.mxid and puppet.can_auto_login(self.mxid):
                self.log.info("Automatically enabling custom puppet")
                await puppet.switch_mxid(access_token="auto", mxid=self.mxid)
        except Exception:
            self.user_profile_cache = None
            self.log.exception("Failed to automatically enable custom puppet")

        await self.create_or_update_space()
        await self.sync_threads()
        self.start_listen()

    async def logout(self):
        self.log.info("Logging out")
        self._is_logged_in = False
        self._is_logging_out = True
        self.stop_listen()
        if self.client:
            self.log.info("Logging out the client.")
            await self.client.logout()
        await self.push_bridge_state(BridgeStateEvent.LOGGED_OUT)
        self._prev_connected_bridge_state = None
        puppet = await pu.Puppet.get_by_li_member_urn(self.li_member_urn, create=False)
        if puppet and puppet.is_real_user:
            await puppet.switch_mxid(None, None)
        if self.li_member_urn:
            try:
                del self.by_li_member_urn[self.li_member_urn]
            except KeyError:
                pass
        await Cookie.delete_all_for_mxid(self.mxid)
        await HttpHeader.delete_all_for_mxid(self.mxid)
        self._track_metric(METRIC_LOGGED_IN, True)
        self.client = None
        self.listener_event_handlers_created = False
        self.user_profile_cache = None
        self.li_member_urn = None
        self.notice_room = None
        await self.save()
        self._is_logging_out = False

    # endregion

    # Spaces support

    async def create_or_update_space(self):
        if not self.config["bridge.space_support.enable"]:
            return

        avatar_state_event_content = {"url": self.config["appservice.bot_avatar"]}
        name_state_event_content = {"name": self.config["bridge.space_support.name"]}

        if self.space_mxid:
            await self.az.intent.send_state_event(
                self.space_mxid, EventType.ROOM_AVATAR, avatar_state_event_content
            )
            await self.az.intent.send_state_event(
                self.space_mxid, EventType.ROOM_NAME, name_state_event_content
            )
        else:
            self.log.debug(f"Creating space for {self.li_member_urn}, inviting {self.mxid}")
            room = await self.az.intent.create_room(
                is_direct=False,
                invitees=[self.mxid],
                creation_content={"type": "m.space"},
                initial_state=[
                    {
                        "type": str(EventType.ROOM_NAME),
                        "content": name_state_event_content,
                    },
                    {
                        "type": str(EventType.ROOM_AVATAR),
                        "content": avatar_state_event_content,
                    },
                ],
            )
            self.space_mxid = room
            await self.save()
            self.log.debug(f"Created space {room}")
            try:
                await self.az.intent.ensure_joined(room)
            except Exception:
                self.log.warning(f"Failed to add bridge bot to new space {room}")

        # Ensure that the user is invited and joined to the space.
        try:
            puppet = await pu.Puppet.get_by_custom_mxid(self.mxid)
            if puppet and puppet.is_real_user:
                await puppet.intent.ensure_joined(self.space_mxid)
        except Exception:
            self.log.warning(f"Failed to add user to the space {self.space_mxid}")

    # endregion

    # region Thread Syncing

    async def get_direct_chats(self) -> dict[UserID, list[RoomID]]:
        assert self.li_member_urn
        return {
            pu.Puppet.get_mxid_from_id(portal.li_other_user_urn): [portal.mxid]
            async for portal in po.Portal.get_all_by_li_receiver_urn(self.li_member_urn)
            if portal.mxid and portal.li_other_user_urn
        }

    @async_time(METRIC_SYNC_THREADS)
    async def sync_threads(self):
        if self._prev_thread_sync + 10 > time.monotonic():
            self.log.debug("Previous thread sync was less than 10 seconds ago, not re-syncing")
            return
        self._prev_thread_sync = time.monotonic()
        try:
            await self._sync_threads()
        except Exception:
            self.log.exception("Failed to sync threads")

    async def _sync_threads(self):
        assert self.client
        sync_count = self.config["bridge.initial_chat_sync"]
        if sync_count <= 0:
            return

        self.log.debug("Fetching threads...")
        await self.push_bridge_state(BridgeStateEvent.BACKFILLING)

        last_activity_before = datetime.now()
        synced_threads = 0
        while True:
            if synced_threads >= sync_count:
                break
            conversations_response = await self.client.get_conversations(
                last_activity_before=last_activity_before
            )
            for conversation in conversations_response.elements:
                if synced_threads >= sync_count:
                    break
                try:
                    await self._sync_thread(conversation)
                except Exception:
                    self.user_profile_cache = None
                    self.log.exception(f"Failed to sync thread {conversation.entity_urn}")
                synced_threads += 1

            await self.update_direct_chats()

            # The page size is 20, by default, so if we get less than 20, we are at the
            # end of the list so we should stop.
            if len(conversations_response.elements) < 20:
                break

            if last_activity_at := conversations_response.elements[-1].last_activity_at:
                last_activity_before = last_activity_at
            else:
                break

        await self.update_direct_chats()

    async def _sync_thread(self, conversation: Conversation):
        self.log.debug(f"Syncing thread {conversation.entity_urn}")

        li_other_user_urn = None
        if not conversation.group_chat:
            other_user = conversation.participants[0]
            if (mm := other_user.messaging_member) and (mp := mm.mini_profile) and mp.entity_urn:
                li_other_user_urn = mp.entity_urn
                if li_other_user_urn == URN("UNKNOWN"):
                    li_other_user_urn = conversation.entity_urn
            else:
                raise Exception("Other chat participant didn't have an entity_urn!")

        portal = await po.Portal.get_by_li_thread_urn(
            conversation.entity_urn,
            li_receiver_urn=self.li_member_urn,
            li_is_group_chat=conversation.group_chat,
            li_other_user_urn=li_other_user_urn,
        )
        assert portal
        portal = cast(po.Portal, portal)

        was_created = False
        if not portal.mxid:
            await portal.create_matrix_room(self, conversation)
            was_created = True
        else:
            await portal.update_matrix_room(self, conversation)
            await portal.backfill(self, conversation, is_initial=False)
        if was_created or not self.config["bridge.tag_only_on_create"]:
            await self._mute_room(portal, conversation.muted)

    async def _mute_room(self, portal: po.Portal, muted: bool):
        if not self.config["bridge.mute_bridging"] or not portal or not portal.mxid:
            return
        puppet = await pu.Puppet.get_by_custom_mxid(self.mxid)
        if not puppet or not puppet.is_real_user:
            return
        if muted:
            await puppet.intent.set_push_rule(
                PushRuleScope.GLOBAL,
                PushRuleKind.ROOM,
                portal.mxid,
                actions=[PushActionType.DONT_NOTIFY],
            )
        else:
            try:
                await puppet.intent.remove_push_rule(
                    PushRuleScope.GLOBAL, PushRuleKind.ROOM, portal.mxid
                )
            except MNotFound:
                pass

    # endregion

    # region Listener and State Management

    async def fill_bridge_state(self, state: BridgeState):
        await super().fill_bridge_state(state)
        if not self.li_member_urn:
            return
        state.remote_id = self.li_member_urn.get_id()
        state.remote_name = ""
        user = await User.get_by_li_member_urn(self.li_member_urn)
        if user and user.client:
            try:
                user_profile = user.user_profile_cache
                if user_profile is not None:
                    self.log.debug("Cache hit on user_profile_cache")
                user_profile = user_profile or await user.client.get_user_profile()
                if mp := user_profile.mini_profile:
                    state.remote_name = " ".join(n for n in [mp.first_name, mp.last_name] if n)
            except Exception:
                self.user_profile_cache = None
                pass

    def stop_listen(self):
        self.log.info("Stopping the listener.")
        if self.listen_task:
            self.log.info("Cancelling the listen task.")
            self.listen_task.cancel()
        self.listen_task = None

    def on_listen_task_end(self, future: Future):
        if future.cancelled():
            self.log.info("Listener task cancelled")
        if self.client and self._is_logged_in and not self.shutdown:
            self.start_listen()
        else:
            # This most likely means that the bridge is being stopped/restarted. But,
            # occasionally, the user gets logged out. In these cases, we want to reset
            # _is_logged_in so the next whoami call does a full call out to LinkedIn to
            # detect whether the user is logged in.
            self.log.warn("No client, not logged in, or shutdown. Not reconnecting.")
            if (
                not self._is_logged_in
                and not self._is_logging_out
                and self.client
                and not self.shutdown
            ):
                self._track_metric(METRIC_CONNECTED, False)
                self.log.warn("Logged out, but not by a logout call, sending bad credentials.")
                asyncio.create_task(self.push_bridge_state(BridgeStateEvent.BAD_CREDENTIALS))
            future.cancel()

    listener_event_handlers_created: bool = False
    listener_task_i: int = 0

    def start_listen(self):
        self.log.info("Starting listener task.")
        self.listen_task = asyncio.create_task(
            self._try_listen(),
            name=f"listener task #{self.listener_task_i}",
        )
        self.listen_task.add_done_callback(self.on_listen_task_end)

    _prev_connected_bridge_state: float | None = None

    async def _try_listen(self):
        self.log.info("Trying to start the listener")
        if not self.client:
            self.log.error("No client, cannot start listener!")
            return
        if not self.listener_event_handlers_created:
            self.log.info("Adding listeners to client")
            self.client.add_event_listener("ALL_EVENTS", self.handle_linkedin_stream_event)
            self.client.add_event_listener("event", self.handle_linkedin_event)
            self.client.add_event_listener("reactionAdded", self.handle_linkedin_reaction_added)
            self.client.add_event_listener("action", self.handle_linkedin_action)
            self.client.add_event_listener("fromEntity", self.handle_linkedin_from_entity)
            self.listener_event_handlers_created = True
        try:
            await self.client.start_listener(self.li_member_urn)
            # Make sure all of the cookies are up-to-date
            await Cookie.bulk_upsert(self.mxid, self.client.cookies())
        except Exception as e:
            self.log.exception(f"Exception in listener: {e}")
            self._prev_connected_bridge_state = None
            self._track_metric(METRIC_CONNECTED, False)
            self.user_profile_cache = None

            if isinstance(e, TooManyRedirects):
                # This means that the user's session is borked (the redirects mean it's trying to
                # redirect to the login page).
                self._is_logged_in = False
                self._is_connected = False
            else:
                await self.push_bridge_state(BridgeStateEvent.TRANSIENT_DISCONNECT, message=str(e))
                await asyncio.sleep(5)

    async def _push_connected_state(self):
        if (
            # We haven't sent a CONNECTED state ever.
            not self._prev_connected_bridge_state
            # We haven't sent a CONNECTED state in the last 12 hours.
            or self._prev_connected_bridge_state + (12 * 60 * 60) < time.monotonic()
        ):
            await self.push_bridge_state(
                BridgeStateEvent.CONNECTED,
                info={"using_headers_from_user": self.client.using_headers_from_user},
            )
            self._prev_connected_bridge_state = time.monotonic()
        else:
            self.log.trace("Event received on event stream, but not sending CONNECTED")

    async def handle_linkedin_stream_event(self, _):
        self._track_metric(METRIC_CONNECTED, True)
        await self._push_connected_state()

    async def handle_linkedin_event(self, event: RealTimeEventStreamEvent):
        assert self.client
        assert isinstance(event.event, ConversationEvent)
        assert event.event.entity_urn

        thread_urn, message_urn = map(URN, event.event.entity_urn.id_parts)
        if (
            (e := event.event)
            and (f := e.from_)
            and (mm := f.messaging_member)
            and (mp := mm.mini_profile)
            and (entity_urn := mp.entity_urn)
        ):
            sender_urn = entity_urn
        else:
            raise Exception("Invalid sender: no entity_urn found!", event)

        portal = await po.Portal.get_by_li_thread_urn(
            thread_urn, li_receiver_urn=self.li_member_urn, create=False
        )
        if not portal:
            conversations = await self.client.get_conversations()
            for conversation in conversations.elements:
                if conversation.entity_urn == thread_urn:
                    await self._sync_thread(conversation)
                    break

            # Nothing more to do, since the backfill should handle the message coming
            # in.
            return

        puppet = await pu.Puppet.get_by_li_member_urn(sender_urn)

        await portal.backfill_lock.wait(message_urn)
        await portal.handle_linkedin_message(self, puppet, event.event)

    async def handle_linkedin_reaction_added(self, event: RealTimeEventStreamEvent):
        assert isinstance(event.reaction_summary, ReactionSummary)
        assert isinstance(event.reaction_added, bool)
        assert isinstance(event.actor_mini_profile_urn, URN)
        assert isinstance(event.event_urn, URN)

        thread_urn, message_urn = map(URN, event.event_urn.id_parts)

        portal = await po.Portal.get_by_li_thread_urn(
            thread_urn, li_receiver_urn=self.li_member_urn, create=False
        )
        if not portal:
            conversations = await self.client.get_conversations()
            for conversation in conversations.elements:
                if conversation.entity_urn == thread_urn:
                    await self._sync_thread(conversation)
                    break

            # Nothing more to do, since the backfill should handle the message coming
            # in.
            return

        puppet = await pu.Puppet.get_by_li_member_urn(event.actor_mini_profile_urn)

        await portal.backfill_lock.wait(message_urn)
        if event.reaction_added:
            await portal.handle_linkedin_reaction_add(self, puppet, event)
        else:
            await portal.handle_linkedin_reaction_remove(self, puppet, event)

    async def handle_linkedin_action(self, event: RealTimeEventStreamEvent):
        if event.action != "UPDATE":
            return
        if (
            (raw_conversation := event.conversation)
            and isinstance(raw_conversation, dict)
            and (conversation := Conversation.from_dict(raw_conversation))
            and conversation.read
        ):
            if portal := await po.Portal.get_by_li_thread_urn(
                conversation.entity_urn, li_receiver_urn=self.li_member_urn, create=False
            ):
                await portal.handle_linkedin_conversation_read(self)

    async def handle_linkedin_from_entity(self, event: RealTimeEventStreamEvent):
        if seen_receipt := event.seen_receipt:
            conversation_urn = URN(seen_receipt.event_urn.id_parts[0])
            if portal := await po.Portal.get_by_li_thread_urn(
                conversation_urn, li_receiver_urn=self.li_member_urn, create=False
            ):
                puppet = await pu.Puppet.get_by_li_member_urn(event.from_entity)
                await portal.handle_linkedin_seen_receipt(self, puppet, event)

        if isinstance(event.conversation, str):
            if portal := await po.Portal.get_by_li_thread_urn(
                URN(event.conversation), li_receiver_urn=self.li_member_urn, create=False
            ):
                puppet = await pu.Puppet.get_by_li_member_urn(event.from_entity)
                await portal.handle_linkedin_typing(puppet)

    # endregion
