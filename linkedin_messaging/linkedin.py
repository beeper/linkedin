from typing import Any, AsyncGenerator, Awaitable, Callable, Optional, TypeVar, Union, cast
from collections import defaultdict
from datetime import datetime
import asyncio
import json
import logging

from bs4 import BeautifulSoup
from dataclasses_json.api import DataClassJsonMixin
import aiohttp
import aiohttp.client_exceptions

from .api_objects import (
    URN,
    Conversation,
    ConversationResponse,
    ConversationsResponse,
    Error,
    MessageAttachmentCreate,
    MessageCreate,
    Picture,
    ReactorsResponse,
    RealTimeEventStreamEvent,
    SendMessageResponse,
    UserProfileResponse,
)
from .exceptions import TooManyRequestsError

LINKEDIN_BASE_URL = "https://www.linkedin.com"
LOGIN_URL = f"{LINKEDIN_BASE_URL}/checkpoint/lg/login-submit"
LOGOUT_URL = f"{LINKEDIN_BASE_URL}/uas/logout"
REALTIME_CONNECT_URL = f"{LINKEDIN_BASE_URL}/realtime/connect"
VERIFY_URL = f"{LINKEDIN_BASE_URL}/checkpoint/challenge/verify"
API_BASE_URL = f"{LINKEDIN_BASE_URL}/voyager/api"
CONNECTIVITY_TRACKING_URL = (
    f"{LINKEDIN_BASE_URL}/realtime/realtimeFrontendClientConnectivityTracking"
)


SEED_URL = f"{LINKEDIN_BASE_URL}/login"
"""
URL to seed all of the auth requests
"""


T = TypeVar("T", bound=DataClassJsonMixin)


async def try_from_json(deserialise_to: T, response: aiohttp.ClientResponse) -> T:
    if response.status < 200 or 300 <= response.status:
        try:
            error = Error.from_json(await response.text())
        except Exception:
            raise Exception(
                f"Deserialising to {deserialise_to} failed because response "
                f"was {response.status}. Details: {await response.text()}"
            )
        raise error

    text = await response.text()
    try:
        return deserialise_to.from_json(text)
    except (json.JSONDecodeError, ValueError) as e:
        try:
            error = Error.from_json(text)
        except Exception:
            raise Exception(
                f"Deserialising to {deserialise_to} failed. Error: {e}. " f"Response: {text}."
            )
        raise error


class ChallengeException(Exception):
    pass


class LinkedInMessaging:
    _request_headers = {
        "user-agent": " ".join(
            [
                "Mozilla/5.0 (X11; Linux x86_64)",
                "AppleWebKit/537.36 (KHTML, like Gecko)",
                "Chrome/120.0.0.0 Safari/537.36",
            ]
        ),
        "accept-language": "en-US,en;q=0.9",
        "x-li-lang": "en_US",
        "x-restli-protocol-version": "2.0.0",
        "x-li-track": json.dumps(
            {
                "clientVersion": "1.13.8751",
                "mpVersion": "1.13.8751",
                "osName": "web",
                "timezoneOffset": -7,
                "timezone": "America/Denver",
                "deviceFormFactor": "DESKTOP",
                "mpName": "voyager-web",
                "displayDensity": 1,
                "displayWidth": 2560,
                "displayHeight": 1440,
            }
        ),
        "Authority": "www.linkedin.com",
        "referer": "https://www.linkedin.com/feed/",
        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Linux"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "x-li-page-instance": "urn:li:page:feed_index_index;bcfe9fd6-239a-49e9-af15-44b7e5895eaa",
        "x-li-recipe-accept": "application/vnd.linkedin.normalized+json+2.1",
        "x-li-recipe-map": json.dumps(
            {
                "inAppAlertsTopic": "com.linkedin.voyager.dash.deco.identity.notifications.InAppAlert-51",  # noqa: E501
                "professionalEventsTopic": "com.linkedin.voyager.dash.deco.events.ProfessionalEventDetailPage-53",  # noqa: E501
                "topCardLiveVideoTopic": "com.linkedin.voyager.dash.deco.video.TopCardLiveVideo-9",
            }
        ),
    }

    session: aiohttp.ClientSession
    two_factor_payload: dict[str, Any]
    event_listeners: defaultdict[
        str,
        list[
            Union[
                Callable[[RealTimeEventStreamEvent], Awaitable[None]],
                Callable[[asyncio.exceptions.TimeoutError], Awaitable[None]],
                Callable[[Exception], Awaitable[None]],
            ]
        ],
    ]

    _realtime_sesion_id: str = ""

    def __init__(self):
        self.session = aiohttp.ClientSession()
        self.event_listeners = defaultdict(list)

    @staticmethod
    def from_cookies(cookies: dict[str, str]) -> "LinkedInMessaging":
        linkedin = LinkedInMessaging()
        linkedin.session.cookie_jar.update_cookies(cookies)
        linkedin._request_headers["csrf-token"] = cookies["JSESSIONID"].strip('"')
        return linkedin

    def cookies(self) -> dict[str, str]:
        return {c.key: c.value for c in self.session.cookie_jar}

    async def close(self):
        await self.session.close()

    async def _get(self, relative_url: str, **kwargs: Any) -> aiohttp.ClientResponse:
        headers = kwargs.pop("headers", {})
        headers.update(self._request_headers)
        return await self.session.get(API_BASE_URL + relative_url, headers=headers, **kwargs)

    async def _post(self, relative_url: str, **kwargs: Any) -> aiohttp.ClientResponse:
        headers = kwargs.pop("headers", {})
        headers.update(self._request_headers)
        return await self.session.post(API_BASE_URL + relative_url, headers=headers, **kwargs)

    # region Authentication

    @property
    def has_auth_cookies(self) -> bool:
        cookie_names = {c.key for c in self.session.cookie_jar}
        return "li_at" in cookie_names and "JSESSIONID" in cookie_names

    async def logged_in(self) -> bool:
        if not self.has_auth_cookies:
            return False
        try:
            return bool(await self.get_user_profile())
        except Exception as e:
            logging.exception(f"Failed getting the user profile: {e}")
            return False

    async def login_manual(self, cookies: dict[str, str], new_session: bool = True):
        if new_session:
            if self.session:
                await self.session.close()
            self.session = aiohttp.ClientSession()
        self.session.cookie_jar.update_cookies(cookies)
        self._request_headers["csrf-token"] = cookies["JSESSIONID"].strip('"')

    async def login(self, email: str, password: str, new_session: bool = True):
        if new_session:
            if self.session:
                await self.session.close()
            self.session = aiohttp.ClientSession()

        # Get the CSRF token.
        async with self.session.get(SEED_URL) as seed_response:
            if seed_response.status != 200:
                raise Exception("Couldn't open the CSRF seed page")

            soup = BeautifulSoup(await seed_response.text(), "html.parser")
            login_csrf_param = soup.find("input", {"name": "loginCsrfParam"})["value"]

        # Login with username and password
        async with self.session.post(
            LOGIN_URL,
            data={
                "loginCsrfParam": login_csrf_param,
                "session_key": email,
                "session_password": password,
            },
        ) as login_response:
            # Check to see if the user was successfully logged in with just email and
            # password.
            if self.has_auth_cookies:
                for c in self.session.cookie_jar:
                    if c.key == "JSESSIONID":
                        self._request_headers["csrf-token"] = c.value.strip('"')
                return

            # 2FA is required. Throw an exception.
            soup = BeautifulSoup(await login_response.text(), "html.parser")

            # TODO (#1) better detection of 2FA vs bad password
            if soup.find("input", {"name": "challengeId"}):
                self.two_factor_payload = {
                    k: soup.find("input", {"name": k})["value"]
                    for k in (
                        "csrfToken",
                        "pageInstance",
                        "resendUrl",
                        "challengeId",
                        "displayTime",
                        "challengeSource",
                        "requestSubmissionId",
                        "challengeType",
                        "challengeData",
                        "challengeDetails",
                        "failureRedirectUri",
                        "flowTreeId",
                    )
                }
                self.two_factor_payload["language"] = "en-US"
                self.two_factor_payload["recognizedDevice"] = "on"
                raise ChallengeException()

            # TODO (#1) can we scrape anything from the page?
            raise Exception("Failed to log in.")

    async def enter_2fa(self, two_factor_code: str):
        async with self.session.post(
            VERIFY_URL, data={**self.two_factor_payload, "pin": two_factor_code}
        ):
            if self.has_auth_cookies:
                for c in self.session.cookie_jar:
                    if c.key == "JSESSIONID":
                        self._request_headers["csrf-token"] = c.value.strip('"')
                return
            # TODO (#1) can we scrape anything from the page?
            raise Exception("Failed to log in.")

    async def logout(self) -> bool:
        csrf_token = self._request_headers.get("csrf-token")
        if not csrf_token:
            return True
        response = await self.session.get(
            LOGOUT_URL,
            params={"csrfToken": csrf_token},
            allow_redirects=False,
        )
        return response.status == 303

    # endregion

    # region Conversations

    async def get_conversations(
        self,
        last_activity_before: Optional[datetime] = None,
    ) -> ConversationsResponse:
        """
        Fetch list of conversations the user is in.

        :param last_activity_before: :class:`datetime` of the last chat activity to
            consider
        """
        if last_activity_before is None:
            last_activity_before = datetime.now()

        params = {
            "keyVersion": "LEGACY_INBOX",
            # For some reason, createdBefore is the key, even though that makes
            # absolutely no sense whatsoever.
            "createdBefore": int(last_activity_before.timestamp() * 1000),
        }

        res = await self._get("/messaging/conversations", params=params)
        return cast(ConversationsResponse, await try_from_json(ConversationsResponse, res))

    async def get_all_conversations(self) -> AsyncGenerator[Conversation, None]:
        """
        A generator of all of the user's conversations using paging.
        """
        last_activity_before = datetime.now()
        while True:
            conversations_response = await self.get_conversations(
                last_activity_before=last_activity_before
            )
            for c in conversations_response.elements:
                yield c

            # The page size is 20, by default, so if we get less than 20, we are at the
            # end of the list so we should stop.
            if len(conversations_response.elements) < 20:
                break

            if last_activity_at := conversations_response.elements[-1].last_activity_at:
                last_activity_before = last_activity_at
            else:
                break

    async def get_conversation(
        self,
        conversation_urn: URN,
        created_before: Optional[datetime] = None,
    ) -> ConversationResponse:
        """
        Fetch the given conversation.

        :param conversation_urn_id: LinkedIn URN for a conversation
        :param created_before: datetime of the last chat activity to consider
        """
        if len(conversation_urn.id_parts) != 1:
            raise TypeError(f"Invalid conversation URN {conversation_urn}.")

        if created_before is None:
            created_before = datetime.now()

        params = {
            "createdBefore": int(created_before.timestamp() * 1000),
        }

        res = await self._get(
            f"/messaging/conversations/{conversation_urn.id_parts[0]}/events",
            params=params,
        )
        return cast(ConversationResponse, await try_from_json(ConversationResponse, res))

    async def mark_conversation_as_read(self, conversation_urn: URN) -> bool:
        res = await self._post(
            f"/messaging/conversations/{conversation_urn.id_parts[-1]}",
            json={"patch": {"$set": {"read": True}}},
        )
        return res.status == 200

    # endregion

    # region Messages

    async def upload_media(
        self,
        data: bytes,
        filename: str,
        media_type: str,
    ) -> MessageAttachmentCreate:
        upload_metadata_response = await self._post(
            "/voyagerMediaUploadMetadata",
            params={"action": "upload"},
            json={
                "mediaUploadType": "MESSAGING_PHOTO_ATTACHMENT",
                "fileSize": len(data),
                "filename": filename,
            },
        )
        if upload_metadata_response.status != 200:
            raise Exception("Failed to send upload metadata.")

        upload_metadata_response_json = (await upload_metadata_response.json()).get("value", {})
        upload_url = upload_metadata_response_json.get("singleUploadUrl")
        if not upload_url:
            raise Exception("No upload URL provided")

        upload_response = await self.session.put(upload_url, data=data)
        if upload_response.status != 201:
            # TODO (#2) is there any other data that we get?
            raise Exception("Failed to upload file.")

        return MessageAttachmentCreate(
            len(data),
            URN(upload_metadata_response_json.get("urn")),
            media_type,
            filename,
        )

    async def send_message(
        self,
        conversation_urn_or_recipients: Union[URN, list[URN]],
        message_create: MessageCreate,
    ) -> SendMessageResponse:
        params = {"action": "create"}
        message_create_key = "com.linkedin.voyager.messaging.create.MessageCreate"

        message_event: dict[str, Any] = {
            "eventCreate": {"value": {message_create_key: message_create.to_dict()}}
        }

        if isinstance(conversation_urn_or_recipients, list):
            message_event["recipients"] = [r.get_id() for r in conversation_urn_or_recipients]
            message_event["subtype"] = "MEMBER_TO_MEMBER"
            payload = {
                "keyVersion": "LEGACY_INBOX",
                "conversationCreate": message_event,
            }
            res = await self._post(
                "/messaging/conversations",
                params=params,
                json=payload,
            )
        else:
            conversation_id = conversation_urn_or_recipients.get_id()
            res = await self._post(
                f"/messaging/conversations/{conversation_id}/events",
                params=params,
                json=message_event,
            )

        return cast(SendMessageResponse, await try_from_json(SendMessageResponse, res))

    async def delete_message(self, conversation_urn: URN, message_urn: URN) -> bool:
        res = await self._post(
            "/messaging/conversations/{}/events/{}".format(
                conversation_urn, message_urn.id_parts[-1]
            ),
            params={"action": "recall"},
        )
        return res.status == 204

    async def download_linkedin_media(self, url: str) -> bytes:
        async with self.session.get(url) as media_resp:
            if not media_resp.ok:
                raise Exception(f"Failed downloading media. Response code {media_resp.status}")
            return await media_resp.content.read()

    # endregion

    # region Reactions

    async def add_emoji_reaction(
        self,
        conversation_urn: URN,
        message_urn: URN,
        emoji: str,
    ) -> bool:
        res = await self._post(
            "/messaging/conversations/{}/events/{}".format(
                conversation_urn, message_urn.id_parts[-1]
            ),
            params={"action": "reactWithEmoji"},
            json={"emoji": emoji},
        )
        return res.status == 204

    async def remove_emoji_reaction(
        self,
        conversation_urn: URN,
        message_urn: URN,
        emoji: str,
    ) -> bool:
        res = await self._post(
            "/messaging/conversations/{}/events/{}".format(
                conversation_urn, message_urn.id_parts[-1]
            ),
            params={"action": "unreactWithEmoji"},
            json={"emoji": emoji},
        )
        return res.status == 204

    async def get_reactors(self, message_urn: URN, emoji: str) -> ReactorsResponse:
        params = {
            "decorationId": "com.linkedin.voyager.dash.deco.messaging.FullReactor-8",
            "emoji": emoji,
            "messageUrn": f"urn:li:fsd_message:{message_urn.id_parts[-1]}",
            "q": "messageAndEmoji",
        }
        res = await self._get("/voyagerMessagingDashReactors", params=params)
        return cast(ReactorsResponse, await try_from_json(ReactorsResponse, res))

    # endregion

    # region Typing Notifications

    async def set_typing(self, conversation_urn: URN):
        await self._post(
            "/messaging/conversations",
            params={"action": "typing"},
            json={"conversationId": conversation_urn.get_id()},
        )

    # endregion

    # region Profiles

    async def get_user_profile(self) -> UserProfileResponse:
        res = await self._get("/me")
        return cast(UserProfileResponse, await try_from_json(UserProfileResponse, res))

    async def download_profile_picture(self, picture: Picture) -> bytes:
        if not picture.vector_image:
            raise Exception(
                "Failed downloading media. Invalid Picture object with no vector_image."
            )
        url = (
            picture.vector_image.root_url
            + picture.vector_image.artifacts[-1].file_identifying_url_path_segment
        )
        async with await self.session.get(url) as profile_resp:
            if not profile_resp.ok:
                raise Exception(f"Failed downloading media. Response code {profile_resp.status}")
            return await profile_resp.content.read()

    # endregion

    # region Event Listener

    def add_event_listener(
        self,
        payload_key: str,
        fn: Union[
            Callable[[RealTimeEventStreamEvent], Awaitable[None]],
            Callable[[asyncio.exceptions.TimeoutError], Awaitable[None]],
            Callable[[Exception], Awaitable[None]],
        ],
    ):
        """
        There are two special event types:

        * ``ALL_EVENTS`` - an event fired on every event, and which contains the entirety of the
          raw event payload
        * ``TIMEOUT`` - an event fired if the event listener connection times out
        """
        self.event_listeners[payload_key].append(fn)

    async def _fire(self, payload_key: str, event: Any):
        for listener in self.event_listeners[payload_key]:
            try:
                await listener(event)
            except Exception:
                logging.exception(f"Listener {listener} failed to handle {event}")

    async def _listen_to_event_stream(self):
        logging.info("Starting event stream listener")

        headers = {"accept": "text/event-stream", **self._request_headers}

        async with self.session.get(
            REALTIME_CONNECT_URL,
            headers=headers,
            params={"rc": "1"},
        ) as resp:
            if resp.status != 200:
                raise TooManyRequestsError(f"Failed to connect. Status {resp.status}.")

            while True:
                line = await resp.content.readline()
                if resp.content.at_eof():
                    break

                if not line.startswith(b"data:"):
                    continue
                data = json.loads(line.decode("utf-8")[6:])

                # Special handling for ALL_EVENTS handler.
                if all_events_handlers := self.event_listeners.get("ALL_EVENTS"):
                    for handler in all_events_handlers:
                        try:
                            await handler(data)
                        except Exception:
                            logging.exception(f"Handler {handler} failed to handle {data}")

                if cc := data.get("com.linkedin.realtimefrontend.ClientConnection", {}):
                    logging.info(f"Got realtime connection ID: {cc.get('id')}")
                    self._request_headers["x-li-realtime-session"] = cc.get("id")
                    self._realtime_sesion_id = cc.get("id")

                event_payload = data.get("com.linkedin.realtimefrontend.DecoratedEvent", {}).get(
                    "payload", {}
                )

                for key in self.event_listeners.keys():
                    if event_payload.get(key) is not None:
                        await self._fire(key, RealTimeEventStreamEvent.from_dict(event_payload))

        logging.info("Event stream closed")

    async def _send_heartbeat(self, user_urn: URN):
        logging.info("Starting heartbeat task")
        while True:
            await asyncio.sleep(60)
            logging.info("Sending heartbeat")

            if not self._realtime_sesion_id:
                logging.warning("No realtime session ID. Skipping heartbeat.")
                continue

            await self._post(
                CONNECTIVITY_TRACKING_URL,
                params={"action": "sendHeartbeat"},
                json={
                    "isFirstHeartbeat": False,
                    "isLastHeartbeat": False,
                    "realtimeSessionId": self._realtime_sesion_id,
                    "mpName": "voyager-web",
                    "mpVersion": "1.13.8094",
                    "clientId": "voyager-web",
                    "actorUrn": str(user_urn),
                    "contextUrns": [str(user_urn)],
                },
            )

    async def start_listener(self, user_urn: URN):
        while True:
            try:
                self._heartbeat_task = asyncio.create_task(self._send_heartbeat(user_urn))
                await self._listen_to_event_stream()
            except asyncio.exceptions.TimeoutError as te:
                # Special handling for TIMEOUT handler.
                if timeout_handlers := self.event_listeners.get("TIMEOUT"):
                    for handler in timeout_handlers:
                        try:
                            await handler(te)
                        except Exception:
                            logging.exception(f"Handler {handler} failed to handle {te}")
            except Exception as e:
                logging.exception(f"Got exception in listener: {e}")
                raise
            finally:
                if not self._heartbeat_task.done():
                    self._heartbeat_task.cancel()

    # endregion
