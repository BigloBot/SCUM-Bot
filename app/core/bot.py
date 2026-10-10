import logging
import discord
from discord.ext import commands
from app.core.config import Config
from app.features.airfield.cog import register

logger = logging.getLogger(__name__)

class ScumBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix=Config.COMMAND_PREFIX, intents=intents)

        # Explicit routing registration on boot
        register(self)

    async def setup_hook(self):
        """Syncs application command tree globally with Discord on boot."""
        await self.tree.sync()
        print("[+] Discord command tree synced successfully.")

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Keeps Discord-facing errors short and generic; details go to the logs."""
        error = getattr(error, "original", error)

        if isinstance(error, commands.CommandNotFound):
            return

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