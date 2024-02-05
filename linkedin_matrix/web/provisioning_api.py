from typing import Any, Awaitable
import json
import logging

from aiohttp import web

from mautrix.types import UserID
from mautrix.util.logging import TraceLogger

from .. import user as u
from ..analytics import track


class ProvisioningAPI:
    log: TraceLogger = logging.getLogger("mau.web.provisioning")
    app: web.Application

    def __init__(self, shared_secret: str):
        self.app = web.Application()
        self.shared_secret = shared_secret
        self.app.router.add_get("/api/whoami", self.status)
        self.app.router.add_options("/api/login", self.login_options)
        self.app.router.add_post("/api/login", self.login)
        self.app.router.add_post("/api/logout", self.logout)

    @property
    def _acao_headers(self) -> dict[str, str]:
        return {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
        }

    @property
    def _headers(self) -> dict[str, str]:
        return {
            **self._acao_headers,
            "Content-Type": "application/json",
        }

    async def login_options(self, _) -> web.Response:
        return web.Response(status=200, headers=self._headers)

    def check_token(self, request: web.Request) -> Awaitable["u.User"]:
        try:
            token = request.headers["Authorization"]
            token = token[len("Bearer ") :]
        except KeyError:
            raise web.HTTPBadRequest(
                body='{"error": "Missing Authorization header"}', headers=self._headers
            )
        except IndexError:
            raise web.HTTPBadRequest(
                body='{"error": "Malformed Authorization header"}',
                headers=self._headers,
            )
        if token != self.shared_secret:
            raise web.HTTPForbidden(body='{"error": "Invalid token"}', headers=self._headers)
        try:
            user_id = request.query["user_id"]
        except KeyError:
            raise web.HTTPBadRequest(
                body='{"error": "Missing user_id query param"}', headers=self._headers
            )

        return u.User.get_by_mxid(UserID(user_id))

    async def status(self, request: web.Request) -> web.Response:
        try:
            user = await self.check_token(request)
        except web.HTTPError as e:
            return e

        data: dict[str, Any] = {
            "permissions": user.permission_level,
            "mxid": user.mxid,
            "linkedin": None,
        }
        if await user.is_logged_in() and user.client:
            user_profile = user.user_profile_cache
            if user_profile is not None:
                self.log.debug("Cache hit on user_profile_cache")
            user_profile = user_profile or await user.client.get_user_profile()
            data["linkedin"] = user_profile.to_dict()

        return web.json_response(data, headers=self._acao_headers)

    async def login(self, request: web.Request) -> web.Response:
        try:
            user = await self.check_token(request)
        except web.HTTPError as e:
            return e

        track(user, "$login_start")
        try:
            req_data = await request.json()
        except json.JSONDecodeError:
            return web.HTTPBadRequest(body='{"error": "Malformed JSON"}', headers=self._headers)

        cookie_dict = {}
        headers = {}

        def parse_cookies(c):
            for cookie in c.split("; "):
                key, val = cookie.split("=", 1)
                cookie_dict[key] = val
            logging.info(f"Got cookies: {cookie_dict.keys()}")

        if "all_headers" in req_data:
            all_headers = req_data["all_headers"]
            logging.info(f"Got headers: {all_headers.keys()}")

            cookies = all_headers.pop("Cookie", all_headers.pop("cookie", None))
            if not cookies:
                return web.HTTPBadRequest(
                    body='{"error": "Missing cookies"}', headers=self._headers
                )

            parse_cookies(cookies)

            # We never want the accept header, skip it
            all_headers.pop("Accept", None)
            all_headers.pop("accept", None)

            # Save the rest of the headers
            headers = all_headers
        elif "cookie_header" in req_data:
            parse_cookies(req_data["cookie_header"])
        elif "li_at" in req_data and "JSESSIONID" in req_data:
            # The request is just a dictionary of individual cookies
            cookie_dict = req_data
            logging.info(f"Legacy login, got cookies: {cookie_dict.keys()}")

        if "li_at" not in cookie_dict or "JSESSIONID" not in cookie_dict:
            return web.HTTPBadRequest(body='{"error": "Missing keys"}', headers=self._headers)

        try:
            await user.on_logged_in(cookie_dict, headers)
            track(user, "$login_success")
        except Exception as e:
            track(user, "$login_failed", {"error": str(e)})
            self.log.exception("Failed to log in", exc_info=True)
            return web.HTTPUnauthorized(
                body='{"error": "LinkedIn authorization failed"}', headers=self._headers
            )
        return web.Response(body="{}", status=200, headers=self._headers)

    async def logout(self, request: web.Request) -> web.Response:
        try:
            user = await self.check_token(request)
            if user.client:
                await user.logout()
        except web.HTTPError:
            pass

        return web.json_response({}, headers=self._acao_headers)
