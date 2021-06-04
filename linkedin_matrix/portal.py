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

from mautrix.bridge import BasePortal

if TYPE_CHECKING:
    from .__main__ import LinkedInBridge
    from .matrix import MatrixHandler


class Portal(BasePortal):
    pass

    @classmethod
    def init_cls(cls, bridge: "LinkedInBridge") -> None:
        BasePortal.bridge = bridge
        cls.az = bridge.az
        cls.config = bridge.config
        cls.loop = bridge.loop
        cls.matrix = bridge.matrix
        # cls.invite_own_puppet_to_pm = cls.config["bridge.invite_own_puppet_to_pm"]
        # NotificationDisabler.puppet_cls = p.Puppet
        # NotificationDisabler.config_enabled = cls.config[
        #     "bridge.backfill.disable_notifications"
        # ]
