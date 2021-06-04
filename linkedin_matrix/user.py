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

from mautrix.bridge import BaseUser, async_getter_lock
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

from .db import User as DBUser

if TYPE_CHECKING:
    from .__main__ import LinkedInBridge


class User(DBUser, BaseUser):
    by_mxid: Dict[UserID, "User"] = {}
    by_li_urn: Dict[str, "User"] = {}

    def __init__(self, mxid: UserID, li_urn: Optional[str] = None):
        super().__init__(mxid=mxid, li_urn=li_urn)
        pass

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

    def _add_to_cache(self) -> None:
        self.by_mxid[self.mxid] = self
        if self.li_urn:
            self.by_li_urn[self.li_urn] = self

    @classmethod
    async def all_logged_in(cls) -> AsyncGenerator["User", None]:
        users = await super().all_logged_in()
        print("User.all_logged_in", users)
        for user in cast(List[cls], users):
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
        from . import portal as po, puppet as pu
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

    async def load_session(
        self,
        _override: bool = False,
        _raise_errors: bool = False,
    ) -> bool:
        pass
