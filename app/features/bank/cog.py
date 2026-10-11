from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from app.core import settings
from app.core.permissions import has_admin
from app.features.bank.board import BANK_CHANNEL_KEY, rebuild_board
from app.features.bank.permissions import BANK_OFFICER_ROLE_KEY


def register(bot: commands.Bot, scum: commands.HybridGroup):
    @scum.group(name="bank", description="Officer stockpiles and rare materials.")
    async def bank(ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send("Try `/scum bank config`.", ephemeral=True)

    @bank.command(name="config", description="View or change bank settings (admins only).")
    @app_commands.describe(
        channel="Channel for the bank control panel and stockpile panels. Run again to rebuild it.",
        officer_role="Role allowed to use the bank controls."
    )
    @commands.guild_only()
    @has_admin()
    async def config(
        ctx: commands.Context,
        channel: Optional[discord.TextChannel] = None,
        officer_role: Optional[discord.Role] = None
    ):
        no_pings = discord.AllowedMentions.none()

        # With no options, just show the current settings.
        if channel is None and officer_role is None:
            channel_id = settings.get_setting(BANK_CHANNEL_KEY)
            role_id = settings.get_setting(BANK_OFFICER_ROLE_KEY)
            await ctx.send(
                "**Bank settings**\n"
                f"Channel: {f'<#{channel_id}>' if channel_id else 'not set'}\n"
                f"Officer role: {f'<@&{role_id}>' if role_id else 'not set (admins only)'}\n"
                f"Active war: **War {settings.get_active_war()}** (change it with `/scum war`)",
                ephemeral=True,
                allowed_mentions=no_pings
            )
            return

        await ctx.defer(ephemeral=True)
        changes = []

        if officer_role is not None:
            settings.set_setting(BANK_OFFICER_ROLE_KEY, str(officer_role.id))
            changes.append(f"Bank officer role set to {officer_role.mention}.")

        # Posting a channel (re)builds the whole board: control panel first, then each stockpile's panel.
        if channel is not None:
            if await rebuild_board(ctx.guild, channel=channel) == "failed":
                changes.append(
                    f"Couldn't post in {channel.mention}. "
                    "Check that the bot can view the channel, send messages and embed links there."
                )
            else:
                changes.append(f"Bank board posted in {channel.mention}.")

        await ctx.send("\n".join(changes), ephemeral=True, allowed_mentions=no_pings)
