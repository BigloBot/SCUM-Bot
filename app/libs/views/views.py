"""Shared Discord view building blocks and input patterns."""
import logging
import re

import discord
from discord import ui

from app.libs.content.text import clip
from app.libs.discord.limits import MAX_OPTION_DESCRIPTION, MAX_OPTION_LABEL, MAX_SELECT_OPTIONS
from app.libs.discord.responses import Responder

logger = logging.getLogger(__name__)

# Stockpile passcodes are exactly six ASCII digits (kept as text so leading zeros survive).
PASSCODE_PATTERN = re.compile(r"[0-9]{6}")

# A whole number of up to 9 digits (matches the form field's max length).
AMOUNT_PATTERN = re.compile(r"[0-9]{1,9}")


class BaseView(ui.View):
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: ui.Item) -> None:
        logger.error("Error in %s.", type(self).__name__, exc_info=(type(error), error, error.__traceback__))
        await Responder(interaction).error()


class FacilitySelect(ui.Select):
    """
    A dropdown of depots or stockpiles (anything with `id`, `name` and `location`). Subclasses pass the
    facilities and implement `on_pick`, which gets the chosen facility's id.
    """

    def __init__(self, facilities, *, placeholder: str, empty_label: str, empty_message: str):
        self.empty_message = empty_message
        options = [
            discord.SelectOption(
                label=clip(f["name"], MAX_OPTION_LABEL),
                value=str(f["id"]),
                description=clip(f"Location: {f['location']}", MAX_OPTION_DESCRIPTION),
            )
            for f in list(facilities)[:MAX_SELECT_OPTIONS]
        ]
        if not options:
            options = [discord.SelectOption(label=empty_label, value="NONE")]
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options)

    async def on_pick(self, interaction: discord.Interaction, facility_id: int) -> None:
        raise NotImplementedError

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "NONE":
            await Responder(interaction).send(self.empty_message)
            return
        await self.on_pick(interaction, int(self.values[0]))
