from typing import cast

from linkedin_messaging import ChallengeException, LinkedInMessaging
from mautrix.bridge import custom_puppet as cpu
from mautrix.bridge.commands import command_handler, HelpSection
from mautrix.client import Client
from mautrix.errors import MForbidden

from .typehint import CommandEvent
from .. import puppet as pu

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
    if not evt.sender.client or not await evt.sender.client.logged_in():
        await evt.reply("You are not logged in")
    else:
        user_profile = await evt.sender.client.get_user_profile()
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
    help_text="Log in to LinkedIn",
    help_args="[_email_]",
)
async def login(evt: CommandEvent):
    if evt.sender.client and await evt.sender.client.logged_in():
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


async def enter_password(evt: CommandEvent):
    try:
        await evt.az.intent.redact(evt.room_id, evt.event_id)
    except MForbidden:
        pass

    assert evt.sender.command_status
    email = evt.sender.command_status["email"]
    password = evt.content.body
    if not isinstance(password, str):
        await evt.reply("Password was not a string!")
        evt.sender.command_status = None
        return

    # Try to log on
    client = LinkedInMessaging()
    try:
        await client.login(email, password)
    except ChallengeException:
        # 2FA is enabled, need another step.
        evt.sender.command_status = {
            "action": "Login",
            "room_id": evt.room_id,
            "next": enter_2fa_code,
            "client": client,
        }
        await evt.reply(
            "You have two-factor authentication turned on. Please enter the code you "
            "received via SMS or your authenticator app here."
        )
        return
    except Exception:
        evt.sender.command_status = None
        await evt.reply("Failed to log in")
        return

    # We were able to log in successfully without 2FA.
    await evt.sender.on_logged_in(client)
    await evt.reply("Successfully logged in")
    evt.sender.command_status = None


async def enter_2fa_code(evt: CommandEvent):
    assert evt.sender.command_status, "command_status not present in event"

    client = cast(LinkedInMessaging, evt.sender.command_status["client"])
    try:
        await client.enter_2fa("".join(evt.args).strip())
    except Exception as e:
        evt.sender.command_status = None
        await evt.reply(f"Failed to log in: {e}")

    await evt.sender.on_logged_in(client)
    await evt.reply("Successfully logged in")
    evt.sender.command_status = None


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

# region Matrix Puppeting


@command_handler(
    needs_auth=True,
    management_only=True,
    help_args="<_access token_>",
    help_section=SECTION_AUTH,
    help_text="Replace your LinkedIn account's Matrix puppet with your Matrix account",
)
async def login_matrix(evt: CommandEvent):
    puppet = await pu.Puppet.get_by_li_member_urn(evt.sender.li_member_urn)
    _, homeserver = Client.parse_mxid(evt.sender.mxid)
    if homeserver != pu.Puppet.hs_domain:
        await evt.reply("You can't log in with an account on a different homeserver")
        return
    try:
        await puppet.switch_mxid(" ".join(evt.args), evt.sender.mxid)
        await evt.reply(
            "Successfully replaced your LinkedIn account's "
            "Matrix puppet with your Matrix account."
        )
    except cpu.OnlyLoginSelf:
        await evt.reply("You may only log in with your own Matrix account")
    except cpu.InvalidAccessToken:
        await evt.reply("Invalid access token")


@command_handler(
    needs_auth=True,
    management_only=True,
    help_section=SECTION_AUTH,
    help_text="Revert your LinkedIn account's Matrix puppet to the original",
)
async def logout_matrix(evt: CommandEvent):
    puppet = await pu.Puppet.get_by_li_member_urn(evt.sender.li_member_urn)
    if not puppet.is_real_user:
        await evt.reply("You're not logged in with your Matrix account")
        return
    await puppet.switch_mxid(None, None)
    await evt.reply("Restored the original puppet for your LinkedIn account")


# endregion
