from typing import (
    Optional,
    Dict,
    AsyncGenerator,
    AsyncIterable,
    Awaitable,
    Union,
    TYPE_CHECKING,
    cast,
)
from datetime import datetime, timedelta
import asyncio

from yarl import URL

from mautrix.types import UserID, RoomID, SyncToken, ContentURI
from mautrix.appservice import IntentAPI
from mautrix.bridge import BasePuppet, async_getter_lock
from mautrix.util.simple_template import SimpleTemplate

from .config import Config
from .db import Puppet as DBPuppet
from . import user as u, portal as p, matrix as m

if TYPE_CHECKING:
    from .__main__ import LinkedInBridge


class Puppet(DBPuppet, BasePuppet):
    mx: m.MatrixHandler
    config: Config
    hs_domain: str
    mxid_template: SimpleTemplate[int]

    by_linkedin_urn: Dict[int, "Puppet"] = {}
    by_custom_mxid: Dict[UserID, "Puppet"] = {}

    @classmethod
    def init_cls(cls, bridge: "LinkedInBridge") -> AsyncIterable[Awaitable[None]]:
        cls.config = bridge.config
        cls.loop = bridge.loop
        cls.mx = bridge.matrix
        cls.az = bridge.az
        cls.hs_domain = cls.config["homeserver.domain"]
        cls.mxid_template = SimpleTemplate(
            cls.config["bridge.username_template"],
            "userid",
            prefix="@",
            suffix=f":{Puppet.hs_domain}",
            type=int,
        )
        cls.sync_with_custom_puppets = cls.config["bridge.sync_with_custom_puppets"]
        cls.homeserver_url_map = {
            server: URL(url)
            for server, url in cls.config["bridge.double_puppet_server_map"].items()
        }
        cls.allow_discover_url = cls.config["bridge.double_puppet_allow_discovery"]
        cls.login_shared_secret_map = {
            server: secret.encode("utf-8")
            for server, secret in cls.config["bridge.login_shared_secret_map"].items()
        }
        cls.login_device_name = "LinkedIn Messages Bridge"

        return (
            puppet.try_start() async for puppet in Puppet.get_all_with_custom_mxid()
        )

    # region Database getters

    @classmethod
    async def get_all_with_custom_mxid(cls) -> AsyncGenerator["Puppet", None]:
        puppets = await super().get_all_with_custom_mxid()
        puppet: cls
        for puppet in puppets:
            try:
                yield cls.by_linkedin_urn[puppet.linkedin_urn]
            except KeyError:
                puppet._add_to_cache()
                yield puppet

    # endregion
