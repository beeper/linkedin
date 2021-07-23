import json
import logging
from typing import Any, Awaitable

from aiohttp import web
from linkedin_messaging import LinkedInMessaging
from mautrix.types import UserID
from mautrix.util.logging import TraceLogger

from .. import user as u


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
            raise web.HTTPForbidden(
                body='{"error": "Invalid token"}', headers=self._headers
            )
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
            data["linkedin"] = (await user.client.get_user_profile()).to_dict()
        return web.json_response(data, headers=self._acao_headers)

    async def login(self, request: web.Request) -> web.Response:
        try:
            user = await self.check_token(request)
        except web.HTTPError as e:
            return e

        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.HTTPBadRequest(
                body='{"error": "Malformed JSON"}', headers=self._headers
            )

        if "li_at" not in data or "JSESSIONID" not in data:
            return web.HTTPBadRequest(
                body='{"error": "Missing keys"}', headers=self._headers
            )

        try:
            client = LinkedInMessaging()
            data["JSESSIONID"] = data["JSESSIONID"].strip('"')
            client.session.cookie_jar.update_cookies(data)
            client.session.headers["csrf-token"] = data["JSESSIONID"]
            await user.on_logged_in(client)
        except Exception:
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
