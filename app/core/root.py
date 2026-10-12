"""The /scum root command and the commands that span every feature."""
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from app.core import settings
from app.core.config import reload_config
from app.core.permissions import ADMIN_ROLE_KEY, has_admin, is_server_owner
from app.features.airfield.panel import refresh_control_panel
from app.features.airfield.service import sync_war_threads
from app.features.bank.board import rebuild_board, resync_board


def register_root(bot: commands.Bot) -> commands.HybridGroup:
    """Creates /scum, adds the cross-feature commands, and returns the group for features to attach to."""

    @bot.hybrid_group(name="scum", description="SCUM bot commands.")
    @commands.guild_only()
    async def scum(ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send("Try `/scum airfield`, `/scum bank`, `/scum config` or `/scum refresh`.", ephemeral=True)

    @scum.command(name="config", description="View or change server-wide settings (admins only).")
    @app_commands.describe(
        war="Active war number, shared by every feature. Switching it locks other wars' depot threads and reopens this war's.",
        admin_role="Role that counts as an admin for every feature, e.g. verified officer (server owner only)."
    )
    @commands.guild_only()
    @has_admin()
    async def config(
        ctx: commands.Context,
        war: Optional[int] = None,
        admin_role: Optional[discord.Role] = None
    ):
        no_pings = discord.AllowedMentions.none()

        # With no options, just show the current settings.
        if war is None and admin_role is None:
            admin_id = settings.get_setting(ADMIN_ROLE_KEY)
            await ctx.send(
                "**Server settings**\n"
                f"Active war: **War {settings.get_active_war()}**\n"
                f"Admin role: {f'<@&{admin_id}>' if admin_id else 'not set (Discord administrators only)'}",
                ephemeral=True,
                allowed_mentions=no_pings
            )
            return

        # Only the server owner may decide who counts as an admin, so an admin can't grant it onwards.
        # Checked before anything is changed, so a refused command changes nothing.
        if admin_role is not None:
            if not is_server_owner(ctx.author):
                await ctx.send("Only the server owner can set the admin role.", ephemeral=True)
                return
            if admin_role.is_default():
                await ctx.send("The admin role can't be @everyone.", ephemeral=True)
                return

        if war is not None and war < 1:
            await ctx.send("The war number must be 1 or higher.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)
        changes = []

        if admin_role is not None:
            settings.set_setting(ADMIN_ROLE_KEY, str(admin_role.id))
            changes.append(f"Admin role set to {admin_role.mention}.")

        if war is not None:
            settings.set_active_war(war)

            # Airfield: every depot thread is brought in line with the new active war, so switching back to
            # an earlier war reopens exactly that war's threads and locks all the others.
            counts = await sync_war_threads(ctx.guild, war)
            line = (
                f"Active war set to **War {war}**. "
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
                line += "\nNote: " + "; ".join(problems) + "."
            changes.append(line)

        await ctx.send("\n".join(changes), ephemeral=True, allowed_mentions=no_pings)

    @scum.command(name="refresh", description="Force the control panel messages to resync (admins only).")
    @commands.guild_only()
    @has_admin()
    async def refresh(ctx: commands.Context):
        await ctx.defer(ephemeral=True)

        try:
            reload_config()
        except Exception:
            pass

        airfield = await refresh_control_panel(ctx.guild)  # also refreshes the kill board under it
        bank = await resync_board(ctx.guild)

        labels = {
            "updated": "refreshed",
            "posted": "reposted",
            "no_channel": "not set up yet",
            "failed": "failed (check the bot's permissions in that channel)",
        }
        await ctx.send(
            "**Resync**\n"
            f"Airfield controls and kill board: {labels[airfield]}\n"
            f"Bank controls and board: {labels[bank]}",
            ephemeral=True
        )

    return scum
