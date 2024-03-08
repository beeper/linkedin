import logging

from mautrix.bridge.commands import HelpSection, command_handler
from mautrix.types import EventType

from ..portal import Portal
from ..puppet import Puppet
from .typehint import CommandEvent

SECTION_SPACES = HelpSection("Miscellaneous", 30, "")


@command_handler(
    needs_auth=True,
    management_only=False,
    help_section=SECTION_SPACES,
    help_text="Synchronize your personal filtering space",
)
async def sync_space(evt: CommandEvent):
    if not evt.bridge.config["bridge.space_support.enable"]:
        await evt.reply("Spaces are not enabled on this instance of the bridge")
        return

    await evt.sender.create_or_update_space()

    if not evt.sender.space_mxid:
        await evt.reply("Failed to create or update space")
        return

    async for portal in Portal.all():
        if not portal.mxid:
            logging.debug(f"Portal {portal} has no mxid")
            continue
        if portal.li_receiver_urn != evt.sender.li_member_urn:
            logging.debug(f"Portal {portal} does not belong to {evt.sender}")
            continue

        logging.debug(f"Adding chat {portal.mxid} to user's space ({evt.sender.space_mxid})")
        try:
            await evt.bridge.az.intent.send_state_event(
                evt.sender.space_mxid,
                EventType.SPACE_CHILD,
                {"via": [evt.bridge.config["homeserver.domain"]], "suggested": True},
                state_key=str(portal.mxid),
            )
        except Exception:
            logging.warning(
                f"Failed to add chat {portal.mxid} to user's space ({evt.sender.space_mxid})"
            )

        if not portal.li_is_group_chat:
            logging.debug(f"Adding puppet {portal.li_other_user_urn} to user's space")
            puppet = await Puppet.get_by_li_member_urn(portal.li_other_user_urn, create=False)
            if not puppet:
                continue
            try:
                await puppet.intent.ensure_joined(evt.sender.space_mxid)
            except Exception as e:
                logging.warning(
                    f"Failed to join {puppet.mxid} to user's space ({evt.sender.space_mxid}): {e}"
                )

    await evt.reply("Synced space")
