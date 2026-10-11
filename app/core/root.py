"""The /scum root command and the commands that span every feature."""
from typing import Optional

from discord import app_commands
from discord.ext import commands
from app.core import settings
from app.core.permissions import has_admin
from app.features.airfield.panel import refresh_control_panel
from app.features.airfield.threads import sync_war_threads
from app.features.bank.board import rebuild_board


def register_root(bot: commands.Bot) -> commands.HybridGroup:
    """Creates /scum, adds the cross-feature commands, and returns the group for features to attach to."""

    @bot.hybrid_group(name="scum", description="SCUM bot commands.")
    @commands.guild_only()
    async def scum(ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send("Try `/scum airfield`, `/scum bank` or `/scum war`.", ephemeral=True)

    @scum.command(name="war", description="Show the active war, or switch to another war (admins only).")
    @app_commands.describe(number="War number to switch to. Leave empty to show the active war.")
    @commands.guild_only()
    @has_admin()
    async def war(ctx: commands.Context, number: Optional[int] = None):
        if number is None:
            await ctx.send(f"The active war is **War {settings.get_active_war()}**.", ephemeral=True)
            return

        if number < 1:
            await ctx.send("The war number must be 1 or higher.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)
        settings.set_active_war(number)

        # Airfield: every depot thread is brought in line with the new active war, so switching back to
        # an earlier war reopens exactly that war's threads and locks all the others.
        counts = await sync_war_threads(ctx.guild, number)
        message = (
            f"Active war set to **War {number}**. "
            f"Depot threads synced: {counts['changed']} updated, {counts['unchanged']} already correct."
        )
        problems = []
        if counts["failed"]:
            problems.append(f"{counts['failed']} could not be updated (check the bot's Manage Threads permission)")
        if counts["missing"]:
            problems.append(f"{counts['missing']} no longer exist in Discord")

        # Keep the war shown on the airfield controls message current.
        await refresh_control_panel(ctx.guild)

        # Bank: show only this war's stockpiles.
        if await rebuild_board(ctx.guild) == "failed":
            problems.append("the bank board couldn't be rebuilt (check the bot's permissions in that channel)")

        if problems:
            message += "\nNote: " + "; ".join(problems) + "."
        await ctx.send(message, ephemeral=True)

    return scum
