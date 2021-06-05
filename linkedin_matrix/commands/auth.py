import requests
from bs4 import BeautifulSoup
from linkedin_api import Linkedin
from mautrix.bridge.commands import command_handler, HelpSection
from mautrix.errors import MForbidden

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
    if not evt.sender.cookies:
        await evt.reply("You are not logged in")
    else:
        linkedin = Linkedin("", "", cookies=evt.sender.cookies)
        user_profile = linkedin.get_user_profile()
        first = user_profile.get("miniProfile", {}).get("firstName")
        last = user_profile.get("miniProfile", {}).get("lastName")
        await evt.reply(f"You are logged in as {first} {last}")


@command_handler(
    needs_auth=False,
    management_only=False,
    help_section=SECTION_AUTH,
    help_text="Log in to LinkedIn",
    help_args="[_email_]",
)
async def login(evt: CommandEvent):
    if evt.sender.cookies:
        await evt.reply("You're already logged in.")
        return

    email = evt.args[0] if len(evt.args) > 0 else None

    if email:
        evt.sender.command_status = {
            "action": "Login",
            "room_id": evt.room_id,
            "next": enter_password,
            "email": email,
        }
        await evt.reply(send_password)
    else:
        await evt.reply(missing_email)


async def enter_password(evt: CommandEvent) -> None:
    try:
        await evt.az.intent.redact(evt.room_id, evt.event_id)
    except MForbidden:
        pass

    email = evt.sender.command_status["email"]
    password = evt.content.body

    # Try to log on
    session = requests.Session()
    text = session.get(SEED_URL).text
    soup = BeautifulSoup(text, "html.parser")
    login_csrf_param = soup.find("input", {"name": "loginCsrfParam"})["value"]
    payload = {
        "session_key": email,
        "loginCsrfParam": login_csrf_param,
        "session_password": password,
    }

    r = session.post(LOGIN_URL, data=payload)
    soup = BeautifulSoup(r.text, "html.parser")

    if (
        "liap" in session.cookies
        and "li_at" in session.cookies
        and "JSESSIONID" in session.cookies
    ):
        # No 2FA necessary.
        await evt.sender.on_logged_in(session.cookies)
        await evt.reply("Successfully logged in")
        return

    # TODO better detection of 2FA vs bad password
    if soup.find("input", {"name": "challengeId"}):
        payload = {
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
            )
        }
        payload["language"] = ("en-US",)

        evt.sender.command_status = {
            "action": "Login",
            "room_id": evt.room_id,
            "next": enter_2fa_code,
            "payload": payload,
            "session": session,
            "email": email,
        }
        await evt.reply(
            "You have two-factor authentication turned on. Please enter the code you "
            "received via SMS or your authenticator app here."
        )
    else:
        evt.sender.command_status = None
        await evt.reply("Failed to log in")


async def enter_2fa_code(evt: CommandEvent) -> None:
    assert evt.sender.command_status, "something went terribly wrong"

    try:
        payload = evt.sender.command_status["payload"]
        payload["pin"] = "".join(evt.args).strip()

        session = evt.sender.command_status["session"]
        r = session.post(VERIFY_URL, data=payload)
        soup = BeautifulSoup(r.text, "html.parser")
        # print(soup)

        if (
            "liap" in session.cookies
            and "li_at" in session.cookies
            and "JSESSIONID" in session.cookies
        ):
            await evt.sender.on_logged_in(session.cookies)
            await evt.reply("Successfully logged in")
            evt.sender.command_status = None
            return

        # TODO actual error handling
        evt.sender.command_status = None
        await evt.reply("Failed to log in")

    except Exception as e:
        evt.log.exception("Failed to log in")
        evt.sender.command_status = None
        await evt.reply(f"Failed to log in: {e}")
