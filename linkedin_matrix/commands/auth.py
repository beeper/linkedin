import logging
import re

from mautrix.bridge.commands import HelpSection, command_handler

from .typehint import CommandEvent

SECTION_AUTH = HelpSection("Authentication", 10, "")

missing_email = "Please use `$cmdprefix+sp login <email>` to log in here."
send_password = "Please send your password here to log in."
send_2fa_code = "Please send the PIN in your inbox here to complete login."

# LinkedIn Login URLs
SEED_URL = "https://www.linkedin.com/uas/login"
LOGIN_URL = "https://www.linkedin.com/checkpoint/lg/login-submit"
VERIFY_URL = "https://www.linkedin.com/checkpoint/challenge/verify"


@command_handler(
    needs_auth=False,
    management_only=False,
    help_section=SECTION_AUTH,
    help_text="See authentication status",
)
async def whoami(evt: CommandEvent):
    assert evt.sender
    user_profile = evt.sender.user_profile_cache
    if user_profile is not None:
        logging.debug("Cache hit on user_profile_cache")
    elif not evt.sender.client or not await evt.sender.client.logged_in():
        await evt.reply("You are not logged in")
        return
    assert evt.sender.client

    user_profile = user_profile or await evt.sender.client.get_user_profile()
    evt.sender.user_profile_cache = user_profile
    if mini_profile := user_profile.mini_profile:
        first = mini_profile.first_name
        last = mini_profile.last_name
        name = f"{first} {last}"
    elif plain_id := user_profile.plain_id:
        name = plain_id
    else:
        await evt.reply("You are not logged in")
        return

    await evt.reply(f"You are logged in as {name}")


# region Login


@command_handler(
    needs_auth=False,
    management_only=False,
    help_section=SECTION_AUTH,
    help_text="""
        Log in to LinkedIn using cookies from an existing LinkedIn browser session. To extract the
        cookies go to your browser developer tools, open the Network tab, then copy the `Cookie`
        header from one of the requests to `https://www.linkedin.com/` and paste the result into
        the command. It is recommended that you use a private window to extract the cookies.
    """,
    help_args="<_cookie header_>",
)
async def login(evt: CommandEvent):
    if evt.sender.client and await evt.sender.client.logged_in():
        await evt.reply("You're already logged in.")
        return

    if len(evt.args) == 0:
        await evt.reply("**Usage:** `$cmdprefix+sp login <cookie header>`")
        return

    await evt.redact()

    cookies: dict[str, str] = {}
    for cookie in evt.args:
        key, val = cookie.strip(" ;").split("=", 1)
        cookies[key] = val

    if not cookies.get("li_at") or not cookies.get("JSESSIONID"):
        await evt.reply("Missing li_at or JSESSIONID cookie")
        return

    try:
        await evt.sender.on_logged_in(cookies, None)
        await evt.reply("Successfully logged in")
    except Exception as e:
        logging.exception("Failed to log in")
        await evt.reply(f"Failed to log in: {e}")
        return


@command_handler(
    needs_auth=False,
    management_only=False,
    help_section=SECTION_AUTH,
    help_text="""
        Log in to LinkedIn using a "Copy as cURL" export from an existing LinkedIn browser session.
    """,
    help_args="<_curl command_>",
)
async def login_curl(evt: CommandEvent):
    # if evt.sender.client and await evt.sender.client.logged_in():
    #     await evt.reply("You're already logged in.")
    #     return

    if len(evt.args) == 0:
        await evt.reply("**Usage:** `$cmdprefix+sp login_curl <cookie header>`")
        return

    # await evt.redact()

    curl_command = " ".join(evt.args)

    cookies: dict[str, str] = {}
    headers: dict[str, str] = {}

    curl_command_regex = r"-H '(?P<key>[^:]+): (?P<value>[^\']+)'"
    header_matches = re.findall(curl_command_regex, curl_command)
    for m in header_matches:
        (name, value) = m

        if name == "cookie":
            cookie_items = value.split("; ")
            for c in cookie_items:
                n, v = c.split("=", 1)
                cookies[n] = v
        elif name == "accept":
            # Every request will have a different value for this
            pass
        else:
            headers[name] = value

    if not cookies.get("li_at") or not cookies.get("JSESSIONID"):
        await evt.reply("Missing li_at or JSESSIONID cookie")
        return

    try:
        await evt.sender.on_logged_in(cookies, headers)
        await evt.reply("Successfully logged in")
    except Exception as e:
        logging.exception("Failed to log in")
        await evt.reply(f"Failed to log in: {e}")
        return


# endregion

# region Log out


@command_handler(
    needs_auth=False,
    management_only=False,
    help_section=SECTION_AUTH,
    help_text="Log out of LinkedIn",
)
async def logout(evt: CommandEvent):
    if not evt.sender.client or not await evt.sender.client.logged_in():
        await evt.reply("You are not logged in.")
        return

    await evt.sender.logout()
    await evt.reply("Successfully logged out")

# endregion
