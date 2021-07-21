import re
from datetime import datetime
from typing import (
    AsyncGenerator,
    AsyncIterable,
    Awaitable,
    cast,
    Optional,
    TYPE_CHECKING,
)

import aiohttp
import magic
from linkedin_messaging import URN
from linkedin_messaging.api_objects import MessagingMember, Picture
from mautrix.appservice import IntentAPI
from mautrix.bridge import async_getter_lock, BasePuppet
from mautrix.types import ContentURI, SyncToken, UserID
from mautrix.util.simple_template import SimpleTemplate
from yarl import URL

from . import matrix as m, portal as p, user as u
from .config import Config
from .db import Puppet as DBPuppet

if TYPE_CHECKING:
    from .__main__ import LinkedInBridge


class Puppet(DBPuppet, BasePuppet):
    mx: m.MatrixHandler
    config: Config
    hs_domain: str
    mxid_template: SimpleTemplate[str]

    by_li_member_urn: dict[URN, "Puppet"] = {}
    by_custom_mxid: dict[UserID, "Puppet"] = {}

    session: aiohttp.ClientSession

    def __init__(
        self,
        li_member_urn: URN,
        name: Optional[str] = None,
        photo_id: Optional[str] = None,
        photo_mxc: Optional[ContentURI] = None,
        name_set: bool = False,
        avatar_set: bool = False,
        is_registered: bool = False,
        custom_mxid: Optional[UserID] = None,
        access_token: Optional[str] = None,
        next_batch: Optional[SyncToken] = None,
        base_url: Optional[URL] = None,
    ):
        super().__init__(
            li_member_urn,
            name,
            photo_id,
            photo_mxc,
            custom_mxid,
            access_token,
            next_batch,
            base_url,
            name_set,
            avatar_set,
            is_registered,
        )
        self._last_info_sync: Optional[datetime] = None

        self.default_mxid = self.get_mxid_from_id(li_member_urn)
        self.default_mxid_intent = self.az.intent.user(self.default_mxid)
        self.intent = self._fresh_intent()

        self.log = self.log.getChild(str(self.li_member_urn))

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
            type=str,
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
        cls.session = aiohttp.ClientSession()

        return (
            puppet.try_start() async for puppet in Puppet.get_all_with_custom_mxid()
        )

    @classmethod
    async def close(cls):
        await cls.session.close()

    def intent_for(self, portal: "p.Portal") -> IntentAPI:
        if portal.li_other_user_urn == self.li_member_urn or (
            portal.backfill_lock.locked
            and self.config["bridge.backfill.invite_own_puppet"]
        ):
            return self.default_mxid_intent
        return self.intent

    # region User info updating

    async def update_info(
        self,
        source: Optional[u.User],
        info: MessagingMember,
        update_avatar: bool = True,
    ) -> "Puppet":
        assert source

        self._last_info_sync = datetime.now()
        try:
            changed = await self._update_name(info)
            if update_avatar:
                photo = info.alternate_image or (
                    info.mini_profile.picture if info.mini_profile else None
                )
                changed = await self._update_photo(photo) or changed

            if changed:
                await self.save()
        except Exception:
            self.log.exception(
                f"Failed to update info from source {source.li_member_urn}"
            )
        return self

    async def reupload_avatar(self, intent: IntentAPI, url: str) -> ContentURI:
        async with self.session.get(url) as req:
            if not req.ok:
                raise Exception(
                    f"Couldn't download avatar for {self.li_member_urn}: {url}"
                )

            image_data = await req.content.read()
            mime = magic.from_buffer(image_data, mime=True)
            return await intent.upload_media(image_data, mime_type=mime)

    async def _update_name(self, info: MessagingMember) -> bool:
        name = self._get_displayname(info)
        if name != self.name or not self.name_set:
            self.name = name
            try:
                await self.default_mxid_intent.set_displayname(self.name)
                self.name_set = True
            except Exception:
                self.log.exception("Failed to set displayname")
                self.name_set = False
            return True
        return False

    @classmethod
    def _get_displayname(cls, info: MessagingMember) -> str:
        if not info.mini_profile:
            raise Exception(f"No mini_profile found for {info.entity_urn}")
        first, last = info.mini_profile.first_name, info.mini_profile.last_name
        info_map = {
            "displayname": info.alternate_name,
            "name": info.alternate_name or f"{first} {last}",
            "first_name": info.alternate_name or first,
            "last_name": last or "",
        }
        for preference in cls.config["bridge.displayname_preference"]:
            pref = info_map.get(preference)
            if pref:
                info_map["displayname"] = pref
                break
        return cls.config["bridge.displayname_template"].format(**info_map)

    photo_id_re = re.compile(r"https://.*?/image/(.*?)/(profile|spinmail)-.*?")

    async def _update_photo(self, picture: Optional[Picture]) -> bool:
        photo_id = None
        if picture and (vi := picture.vector_image):
            match = self.photo_id_re.match(vi.root_url)
            # Handle InMail pictures which don't have any root_url
            if not match and len(vi.artifacts) > 0:
                match = self.photo_id_re.match(
                    vi.artifacts[0].file_identifying_url_path_segment
                )
            if match:
                photo_id = match.group(1)

        if photo_id != self.photo_id or not self.avatar_set:
            self.photo_id = photo_id

            if photo_id and picture and (vi := picture.vector_image):
                largest_artifact = vi.artifacts[-1]
                self.photo_mxc = await self.reupload_avatar(
                    self.default_mxid_intent,
                    (vi.root_url + largest_artifact.file_identifying_url_path_segment),
                )
            else:
                self.photo_mxc = ContentURI("")

            try:
                await self.default_mxid_intent.set_avatar_url(self.photo_mxc)
                self.avatar_set = True
            except Exception:
                self.log.exception("Failed to set avatar")
                self.avatar_set = False

            return True
        return False

    # endregion

    # region Database getters

    def _add_to_cache(self):
        self.by_li_member_urn[self.li_member_urn] = self
        if self.custom_mxid:
            self.by_custom_mxid[self.custom_mxid] = self

    @classmethod
    @async_getter_lock
    async def get_by_li_member_urn(
        cls,
        li_member_urn: URN,
        *,
        create: bool = True,
    ) -> Optional["Puppet"]:
        try:
            return cls.by_li_member_urn[li_member_urn]
        except KeyError:
            pass

        puppet = cast(
            Optional[Puppet], await super().get_by_li_member_urn(li_member_urn)
        )
        if puppet:
            puppet._add_to_cache()
            return puppet

        if create:
            puppet = cls(li_member_urn, None, None, None, False, False)
            await puppet.insert()
            puppet._add_to_cache()
            return puppet

        return None

    @classmethod
    async def get_by_mxid(cls, mxid: UserID, create: bool = True) -> Optional["Puppet"]:
        li_member_urn = cls.get_id_from_mxid(mxid)
        if li_member_urn:
            return await cls.get_by_li_member_urn(li_member_urn, create=create)
        return None

    @classmethod
    @async_getter_lock
    async def get_by_custom_mxid(cls, mxid: UserID) -> Optional["Puppet"]:
        try:
            return cls.by_custom_mxid[mxid]
        except KeyError:
            pass

        puppet = cast("Puppet", await super().get_by_custom_mxid(mxid))
        if puppet:
            puppet._add_to_cache()
            return puppet

        return None

    @classmethod
    async def get_all_with_custom_mxid(cls) -> AsyncGenerator["Puppet", None]:
        puppets = await super().get_all_with_custom_mxid()
        for puppet in cast(list[Puppet], puppets):
            try:
                yield cls.by_li_member_urn[puppet.li_member_urn]
            except KeyError:
                puppet._add_to_cache()
                yield puppet

    @classmethod
    def get_id_from_mxid(cls, mxid: UserID) -> Optional[URN]:
        parsed = cls.mxid_template.parse(mxid)
        return URN(parsed) if parsed else None

    @classmethod
    def get_mxid_from_id(cls, li_member_urn: URN) -> UserID:
        return UserID(cls.mxid_template.format_full(li_member_urn.id_str()))

    # endregion
