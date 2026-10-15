"""Shared Discord view building blocks, interaction responses, and input patterns."""
import logging
import re
import discord
from discord import ui

logger = logging.getLogger(__name__)

# Stockpile passcodes are exactly six ASCII digits (kept as text so leading zeros survive).
PASSCODE_PATTERN = re.compile(r"[0-9]{6}")

# A whole number of up to 9 digits (matches the form field's max length).
AMOUNT_PATTERN = re.compile(r"[0-9]{1,9}")

INTERNAL_ERROR = "An internal error occurred. Please try again, and let an admin know if it keeps happening."

MAX_SELECT_OPTIONS = 5


async def respond_or_followup(interaction: discord.Interaction, content: str, *, ephemeral: bool = True, **kwargs):
    """Reply to an interaction whether or not it has been responded to (or deferred) yet."""
    if interaction.response.is_done():
        return await interaction.followup.send(content, ephemeral=ephemeral, **kwargs)
    return await interaction.response.send_message(content, ephemeral=ephemeral, **kwargs)


async def send_internal_error(interaction: discord.Interaction):
    """Generic error for the user. The details only go to the bot's logs."""
    try:
        await respond_or_followup(interaction, INTERNAL_ERROR)
    except Exception:
        logger.error("Could not deliver the internal error message to the user.")


class BaseView(ui.View):
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: ui.Item) -> None:
        logger.error(f"Error in {type(self).__name__}: {error}", exc_info=(type(error), error, error.__traceback__))
        await send_internal_error(interaction)


class FacilitySelect(ui.Select):
    """
    A dropdown of depots or stockpiles (anything with `id`, `name` and `location`). Subclasses pass the
    facilities and implement `on_pick`, which gets the chosen facility's id.
    """
    def __init__(self, facilities, *, placeholder: str, empty_label: str, empty_message: str):
        self.empty_message = empty_message
        options = [
            discord.SelectOption(label=f["name"][:100], value=str(f["id"]), description=f"Location: {f['location']}"[:100])
            for f in list(facilities)[:MAX_SELECT_OPTIONS]
        ]
        if not options:
            options = [discord.SelectOption(label=empty_label, value="NONE")]
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options)

    async def on_pick(self, interaction: discord.Interaction, facility_id: int) -> None:
        raise NotImplementedError

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "NONE":
            await respond_or_followup(interaction, self.empty_message)
            return
        await self.on_pick(interaction, int(self.values[0]))
