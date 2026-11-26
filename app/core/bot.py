import logging

import discord
from discord import app_commands

from app.core.root import build_root
from app.libs.discord.responses import Responder

from app.features.airfield.feature import feature as airfield
from app.features.bank.feature import feature as bank

logger = logging.getLogger(__name__)

# Features to register with the bot.
FEATURES = (airfield, bank)


class ScumBot(discord.Client):
    """Slash commands only, so no privileged intents are needed."""

    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)
        self.tree.error(self.on_app_command_error)
        self.tree.add_command(build_root(FEATURES))

    async def setup_hook(self):
        """Re-registers the persistent control panel buttons, then syncs the command tree with Discord."""
        for feature in FEATURES:
            for view in feature.persistent_views():
                self.add_view(view)
        await self.tree.sync()
        logger.info("Command tree synced.")

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Keeps Discord-facing errors short and generic; details go to the logs."""
        command = interaction.command.qualified_name if interaction.command else "unknown"

        if isinstance(error, (app_commands.CheckFailure, app_commands.NoPrivateMessage)):
            logger.info("%s (%s) was refused /%s.", interaction.user, interaction.user.id, command)
            await Responder(interaction).send("You don't have permission to use this command.")
            return

        logger.error("Unhandled error in /%s.", command, exc_info=getattr(error, "original", error))
        await Responder(interaction).error()

    async def on_ready(self):
        logger.info("Logged in as %s (%s) - ScumBot online.", self.user.name, self.user.id)
