"""Shared Discord UI building blocks: generic error handling for views and modals."""
import logging
import re
import discord
from discord import ui

logger = logging.getLogger(__name__)

# Stockpile passcodes are exactly six ASCII digits (kept as text so leading zeros survive).
PASSCODE_PATTERN = re.compile(r"[0-9]{6}")

INTERNAL_ERROR = "An internal error occurred. Please try again, and let an admin know if it keeps happening."


async def send_internal_error(interaction: discord.Interaction):
    """Generic error for the user. The details only go to the bot's logs."""
    try:
        if interaction.response.is_done():
            await interaction.followup.send(INTERNAL_ERROR, ephemeral=True)
        else:
            await interaction.response.send_message(INTERNAL_ERROR, ephemeral=True)
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
