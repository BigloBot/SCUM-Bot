"""Shared Discord UI building blocks: error handling, input patterns, and the facility (depot / stockpile) bases."""
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

MAX_SELECT_OPTIONS = 25  # a Discord dropdown holds at most 25 options


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


class BaseModal(ui.Modal):
    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.error(f"Error in {type(self).__name__}: {error}", exc_info=(type(error), error, error.__traceback__))
        await send_internal_error(interaction)


class FacilityModal(BaseModal):
    """
    The "add one" form shared by depots and stockpiles: a name, a six-digit passcode and a location.
    Subclasses set the class attributes below, pass `title=` in the class statement, and implement
    `is_duplicate` and `create`. By the time `create` runs the interaction has been deferred (ephemeral),
    so it should answer with `interaction.followup`.
    """
    noun = "facility"                           # used in the validation messages, e.g. "depot"
    name_label = "Name"
    name_placeholder = ""
    location_label = "Location"
    location_placeholder = "e.g. Callahan's Passage"

    def __init__(self):
        super().__init__()
        self.facility_name = ui.TextInput(
            label=self.name_label, placeholder=self.name_placeholder, required=True, max_length=40)
        self.facility_code = ui.TextInput(
            label="Passcode (6 digits)", placeholder="e.g. 123456", required=True, min_length=6, max_length=6)
        self.facility_location = ui.TextInput(
            label=self.location_label, placeholder=self.location_placeholder, required=True, max_length=40)
        for field in (self.facility_name, self.facility_code, self.facility_location):
            self.add_item(field)

    def is_duplicate(self, name: str) -> bool:
        raise NotImplementedError

    async def create(self, interaction: discord.Interaction, name: str, code: str, location: str) -> None:
        raise NotImplementedError

    async def on_submit(self, interaction: discord.Interaction):
        name = self.facility_name.value.strip()
        code = self.facility_code.value.strip()
        location = self.facility_location.value.strip()

        if not name or not location:
            await respond_or_followup(interaction, f"The {self.noun} name and location can't be empty.")
            return
        if not PASSCODE_PATTERN.fullmatch(code):
            await respond_or_followup(interaction, "The passcode must be exactly 6 digits (0-9).")
            return
        if self.is_duplicate(name):
            await respond_or_followup(interaction, f"A {self.noun} with that name is already active in this war.")
            return

        await interaction.response.defer(ephemeral=True)
        await self.create(interaction, name, code, location)


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
