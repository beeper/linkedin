import asyncio
import time
from typing import (
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
from requests.cookies import RequestsCookieJar

from .config import Config
from .db import User as DBUser

if TYPE_CHECKING:
    from .__main__ import LinkedInBridge


class User(DBUser, BaseUser):
    shutdown: bool = False
    config: Config
    linkedin_client: Linkedin

    by_mxid: Dict[UserID, "User"] = {}
    by_li_urn: Dict[str, "User"] = {}

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

    # region Database getters

    def _add_to_cache(self) -> None:
        self.by_mxid[self.mxid] = self
        if self.li_urn:
            self.by_li_urn[self.li_urn] = self

    @is_connected.setter
    def is_connected(self, val: Optional[bool]) -> None:
        if self._is_connected != val:
            self._is_connected = val
            self._connection_time = time.monotonic()

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
        from . import puppet as pu

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

    async def load_session(
        self,
        _override: bool = False,
        _raise_errors: bool = False,
    ) -> bool:
        if self._is_logged_in and not _override:
            return True
        if not self.cookies:
            return False
        self.linkedin_client = Linkedin("", "", cookies=self.cookies)

    async def is_logged_in(self, _override: bool = False) -> bool:
        return False

    async def on_logged_in(self, cookies: RequestsCookieJar):
        self.cookies = cookies
        self.linkedin_client = Linkedin("", "", cookies=cookies)
        profile = self.linkedin_client.get_user_profile()
        self.li_urn = str(profile["plainId"])  # TODO figure out what this actually is
        await self.save()

    def stop_listen(self) -> None:
        if self.listen_task:
            self.listen_task.cancel()
        self.listen_task = None
