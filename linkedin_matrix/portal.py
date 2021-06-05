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

from mautrix.bridge import BasePortal, NotificationDisabler, async_getter_lock
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


class Portal(DBPortal, BasePortal):
    invite_own_puppet_to_pm: bool = False
    by_mxid: Dict[RoomID, "Portal"] = {}
    by_li_urn: Dict[Tuple[str, str], "Portal"] = {}
    matrix: "MatrixHandler"
    config: Config

    def __init__(
        self,
        li_urn: str,
        li_receiver: str,
        mxid: Optional[RoomID] = None,
        name: Optional[str] = None,
        photo_id: Optional[str] = None,
        avatar_url: Optional[ContentURI] = None,
        encrypted: bool = False,
    ) -> None:
        super().__init__(
            li_urn, li_receiver, mxid, name, photo_id, avatar_url, encrypted
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
        # NotificationDisabler.puppet_cls = p.Puppet
        # NotificationDisabler.config_enabled = cls.config[
        #     "bridge.backfill.disable_notifications"
        # ]

    # region Properties

    @property
    def li_urn_log(self) -> str:
        if self.is_direct:
            return f"{self.li_urn}<->{self.li_receiver}"
        return str(self.li_urn)

    # endregion

    # region Database getters

    async def postinit(self) -> None:
        self.by_li_urn[(self.li_urn, self.li_receiver)] = self
        if self.mxid:
            self.by_mxid[self.mxid] = self
        self._main_intent = (
            (await p.Puppet.get_by_li_urn(self.li_urn)).default_mxid_intent
            if self.is_direct
            else self.az.intent
        )

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
    async def all(cls) -> AsyncGenerator["Portal", None]:
        portals = await super().all()
        for portal in cast(List[Portal], portals):
            try:
                yield cls.by_li_urn[(portal.li_urn, portal.li_receiver)]
            except KeyError:
                await portal.postinit()
                yield portal

    # endregion
