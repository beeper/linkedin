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

from mautrix.bridge import BaseUser
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
    by_linkedin_urn: Dict[str, "User"] = {}

    def __init__(self, mxid: UserID, linkedin_urn: Optional[str] = None):
        super().__init__(mxid=mxid, linkedin_urn=linkedin_urn)
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
        if self.linkedin_urn:
            self.by_linkedin_urn[self.linkedin_urn] = self

    @classmethod
    async def all_logged_in(cls) -> AsyncGenerator["User", None]:
        users = await super().all_logged_in()
        for user in cast(List[cls], users):
            try:
                yield cls.by_mxid[user.mxid]
            except KeyError:
                user._add_to_cache()
                yield user

    async def load_session(
        self,
        _override: bool = False,
        _raise_errors: bool = False,
    ) -> bool:
        pass
