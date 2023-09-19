import logging

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
    help_text=(
        "Log in to LinkedIn by cookies from an existing LinkedIn browser session (recommended "
        "to use a private window to extract the cookies)"
    ),
    help_args="<_li\\_at_> <_jsessionid_>",
)
async def login(evt: CommandEvent):
    if evt.sender.client and await evt.sender.client.logged_in():
        await evt.reply("You're already logged in.")
        return
    elif len(evt.args) != 2:
        await evt.reply("**Usage:** `$cmdprefix+sp login <li_at> <jsessionid>`")
        return

    li_at = evt.args[0].strip('"')
    jsessionid = evt.args[1].strip('"')
    await evt.redact()

    try:
        await evt.sender.on_logged_in(li_at, jsessionid)
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
