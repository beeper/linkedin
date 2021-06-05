import asyncio
import time
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterable,
    Awaitable,
    cast,
    Dict,
    List,
    Optional,
    TYPE_CHECKING,
)

from linkedin_api import Linkedin
from mautrix.bridge import async_getter_lock, BaseUser
from mautrix.errors import MNotFound
from mautrix.types import (
    PushActionType,
    PushRuleKind,
    PushRuleScope,
    UserID,
    RoomID,
    EventID,
    TextMessageEventContent,
    MessageType,
)
from mautrix.util.simple_lock import SimpleLock
from mautrix.util.opt_prometheus import Summary, Gauge, async_time
from requests.cookies import RequestsCookieJar

from . import portal as po, puppet as pu
from .config import Config
from .db import User as DBUser, UserPortal

if TYPE_CHECKING:
    from .__main__ import LinkedInBridge

METRIC_LOGGED_IN = Gauge("bridge_logged_in", "Users logged into the bridge")
METRIC_SYNC_THREADS = Summary("bridge_sync_threads", "calls to sync_threads")


class User(DBUser, BaseUser):
    shutdown: bool = False
    config: Config

    by_mxid: Dict[UserID, "User"] = {}
    by_li_urn: Dict[str, "User"] = {}

    linkedin_client: Linkedin

    _is_connected: Optional[bool]
    _is_logged_in: Optional[bool]
    _is_refreshing: bool
    _notice_room_lock: asyncio.Lock
    _notice_send_lock: asyncio.Lock
    _sync_lock: SimpleLock
    is_admin: bool

    def __init__(
        self,
        mxid: UserID,
        li_urn: Optional[str] = None,
        cookies: Optional[RequestsCookieJar] = None,
        notice_room: Optional[RoomID] = None,
    ):
        super().__init__(mxid, li_urn, cookies, notice_room)
        BaseUser.__init__(self)
        self.notice_room = notice_room
        self._notice_room_lock = asyncio.Lock()
        self._notice_send_lock = asyncio.Lock()

        self.command_status = None
        (
            self.is_whitelisted,
            self.is_admin,
            self.permission_level,
        ) = self.config.get_permissions(mxid)
        self._is_logged_in = None
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
    def init_cls(cls, bridge: "LinkedInBridge") -> AsyncIterable[Awaitable[bool]]:
        cls.bridge = bridge
        cls.config = bridge.config
        cls.az = bridge.az
        cls.loop = bridge.loop
        cls.temp_disconnect_notices = bridge.config[
            "bridge.temporary_disconnect_notices"
        ]
        return (user.load_session() async for user in cls.all_logged_in())

    @property
    def is_connected(self) -> Optional[bool]:
        return self._is_connected

    @is_connected.setter
    def is_connected(self, val: Optional[bool]):
        if self._is_connected != val:
            self._is_connected = val
            self._connection_time = time.monotonic()

    # region Database getters

    def _add_to_cache(self) -> None:
        self.by_mxid[self.mxid] = self
        if self.li_urn:
            self.by_li_urn[self.li_urn] = self

    @classmethod
    async def all_logged_in(cls) -> AsyncGenerator["User", None]:
        users = await super().all_logged_in()
        for user in cast(List["User"], users):
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
    ) -> Optional["User"]:
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
    async def get_by_li_urn(cls, li_urn: str) -> Optional["User"]:
        try:
            return cls.by_li_urn[li_urn]
        except KeyError:
            pass

        user = cast("User", await super().get_by_li_urn(li_urn))
        if user is not None:
            user._add_to_cache()
            return user

        return None

    # endregion

    # region Session Management

    async def load_session(
        self,
        _override: bool = False,
        _raise_errors: bool = False,
    ) -> bool:
        if self._is_logged_in and not _override:
            return True
        if not self.cookies:
            return False
        linkedin_client = Linkedin("", "", cookies=self.cookies)
        # TODO check if it actually is logged in
        while True:
            try:
                user_info = linkedin_client.get_user_profile()
                break
            except Exception as e:
                print(e)
                return False

        if not user_info:
            return False

        self.log.info("Loaded session successfully")
        self.li_urn = str(user_info["plainId"])  # TODO figure out what this actually is
        self.linkedin_client = linkedin_client
        self._track_metric(METRIC_LOGGED_IN, True)
        self._is_logged_in = True
        self.is_connected = None
        self.stop_listen()
        asyncio.create_task(self.post_login())
        return True

    async def is_logged_in(self, _override: bool = False) -> bool:
        if not self.cookies or not self.linkedin_client:
            return False
        if self._is_logged_in is None or _override:
            try:
                self._is_logged_in = bool(self.linkedin_client.get_user_profile())
            except Exception:
                self.log.exception("Exception checking login status")
                self._is_logged_in = False
        return self._is_logged_in

    async def on_logged_in(self, cookies: RequestsCookieJar):
        self.cookies = cookies
        self.linkedin_client = Linkedin("", "", cookies=cookies)
        profile = self.linkedin_client.get_user_profile()
        self.li_urn = str(profile["plainId"])  # TODO figure out what this actually is
        await self.save()

    async def post_login(self):
        self.log.info("Running post-login actions")
        self._add_to_cache()

        try:
            puppet = await pu.Puppet.get_by_li_urn(self.li_urn)

            if puppet.custom_mxid != self.mxid and puppet.can_auto_login(self.mxid):
                self.log.info("Automatically enabling custom puppet")
                await puppet.switch_mxid(access_token="auto", mxid=self.mxid)
        except Exception:
            self.log.exception("Failed to automatically enable custom puppet")
        await self.sync_threads()
        self.start_listen()

    # endregion

    # region Thread Syncing

    async def get_direct_chats(self) -> Dict[UserID, List[RoomID]]:
        # TODO
        return {}
        return {
            pu.Puppet.get_mxid_from_id(portal.fbid): [portal.mxid]
            async for portal in po.Portal.get_all_by_receiver(self.fbid)
            if portal.mxid
        }

    @async_time(METRIC_SYNC_THREADS)
    async def sync_threads(self):
        if self._prev_thread_sync + 10 > time.monotonic():
            self.log.debug(
                "Previous thread sync was less than 10 seconds ago, not re-syncing"
            )
            return
        self._prev_thread_sync = time.monotonic()
        try:
            await self._sync_threads()
        except Exception:
            self.log.exception("Failed to sync threads")

    async def _sync_threads(self) -> None:
        sync_count = self.config["bridge.initial_chat_sync"]
        self.log.debug("Fetching threads...")
        user_portals = await UserPortal.all(self.li_urn)

        # TODO: implement page limit support in linkedin-api, and also get more pages if
        # necessary
        conversations = self.linkedin_client.get_conversations()

        if sync_count <= 0:
            return

        for conversation in conversations.get("elements", []):
            try:
                await self._sync_thread(conversation, user_portals)
            except Exception:
                self.log.exception(
                    "Failed to sync thread %s", conversation.get("entityUrn")
                )

        await self.update_direct_chats()

    async def _sync_thread(
        self,
        conversation: Dict[str, Any],
        user_portals: Dict[str, UserPortal],
    ):
        urn = cast(str, conversation.get("entityUrn"))
        is_direct = not conversation.get("groupChat", False)
        self.log.debug(f"Syncing thread {urn}")
        portal = await po.Portal.get_by_thread(urn, self.li_urn)
        assert portal
        portal = cast(po.Portal, portal)

        was_created = False
        if not portal.mxid:
            await portal.create_matrix_room(self, conversation)
            was_created = True
        else:
            await portal.update_matrix_room(self, conversation)
            await portal.backfill(self, is_initial=False, conversation=conversation)
        if was_created or not self.config["bridge.tag_only_on_create"]:
            await self._mute_room(portal, conversation.get("muted", False))

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

    # region Listener Management

    def stop_listen(self):
        if self.listen_task:
            self.listen_task.cancel()
        self.listen_task = None

    def start_listen(self):
        self.listen_task = asyncio.create_task(self._try_listen())

    async def _try_listen(self):
        try:
            print("listen")
        except Exception as e:
            print(e)

    # endregion
