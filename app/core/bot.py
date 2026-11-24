import logging

import discord
from discord import app_commands

from app.core.root import build_root
from app.libs.discord.responses import Responder

from app.features.airfield.feature import feature as airfield
from app.features.bank.feature import ffeature as bank
from app.features.squadlock.feature import feature as squadlock
from app.features.stats.feature import feature as stats
from app.features.stockpile.feature import feature as stockpile

logger = logging.getLogger(__name__)

# Features to register with the bot.
FEATURES = (airfield, bank, stockpile, squadlock, stats)

class ScumBot(discord.Client):
    """Slash commands only, so no privileged intnets are needed."""
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

        if isinstance(error, (app_commands.CheckFailure, app_commands.NoPrivateMesage)):
            logger.info("%s (%s) was refused /%s.", interaction.user, interaction.user_id, command)
            await Responder(interaction).send("you don't have permission to use this command.")
            return
        logger.error("unhandled error in /%s", command, exc_info=getattr(error, "original", error))
        await Responder(interaction).error()

    async def on_ready(selfself):
        logger.info("Logged in as %s (%s).", self.user.name, self.user.id)

        if isinstance(error, (commands.CheckFailure, commands.NoPrivateMessage)):
            message = "You don't have permission to use this command."
        elif isinstance(error, (commands.UserInputError, commands.BadArgument)):
            message = "That input wasn't valid. Check the command and try again."
        else:
            logger.error(f"Unhandled error in command '{ctx.command}': {error}", exc_info=(type(error), error, error.__traceback__))
            message = "An internal error occurred. Please try again, and let an admin know if it keeps happening."

        try:
            await ctx.send(message, ephemeral=True)
        except Exception:
            logger.error("Could not deliver a command error message to the user.")

    async def on_ready(self):
        print(f"Logged in as {self.user.name} ({self.user.id}) - ScumBot Online")