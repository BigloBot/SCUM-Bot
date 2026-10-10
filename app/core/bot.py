import discord
from discord.ext import commands
from app.core.config import Config
from app.features.airfield.cog import register

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

    async def on_ready(self):
        print(f"Logged in as {self.user.name} ({self.user.id}) - ScumBot Online")