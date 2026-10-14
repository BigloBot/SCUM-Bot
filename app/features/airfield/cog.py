from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from app.core import settings
from app.core.permissions import has_admin
from app.features.airfield.dashboard import refresh_control_panel
from app.features.airfield.permissions import AIRFIELD_AVIATOR_ROLE_KEY, can_use_airfield
from app.features.airfield.repository import AirfieldRepository
from app.features.airfield.stats import build_production_embed, build_stats_embed


def register(bot: commands.Bot, scum: commands.HybridGroup):
    # Pilot actions all have a button on the permanent controls message; only stats and settings are commands.
    # Everything lives under /scum airfield. Discord only applies command visibility to top-level
    # commands, so /scum stays visible to everyone and permissions are enforced when a command runs.

    @scum.group(name="airfield", description="Airfield depots, stockpiles and flights.")
    async def airfield(ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send("Try `/scum airfield stats` (pilots and production) or `/scum airfield config`. Flights, kills and depots are managed with the controls in the controls channel.", ephemeral=True)

    # ==================== STATS ====================
    @airfield.command(name="stats", description="Top aces, busiest pilots and aircraft production for a war.")
    @app_commands.describe(war="War to show (defaults to the active war).")
    @commands.guild_only()
    async def stats(ctx: commands.Context, war: Optional[int] = None):
        if not can_use_airfield(ctx.author):
            await ctx.send("You don't have permission to use airfield commands.", ephemeral=True)
            return
        war = war if war is not None else settings.get_active_war()
        await ctx.send(
            embeds=[
                build_stats_embed(war, AirfieldRepository.get_pilot_stats(war)),
                build_production_embed(
                    war, AirfieldRepository.get_production_stats(war), AirfieldRepository.get_aircraft_types(),
                    settings.get_active_war()
                ),
            ],
            ephemeral=True
        )

    # ==================== ADMIN CONFIG ====================
    @airfield.command(name="config", description="View or change airfield settings (admins only).")
    @app_commands.describe(
        forum="Forum channel where depot threads are created.",
        controls="Channel that holds the permanent control panel message.",
        aviator_role="Role allowed to use the airfield controls."
    )

    @commands.guild_only()
    @has_admin()
    async def config(
            ctx: commands.Context,
            forum: Optional[discord.ForumChannel] = None,
            controls: Optional[discord.TextChannel] = None,
            aviator_role: Optional[discord.Role] = None
    ):
        no_pings = discord.AllowedMentions.none()

        # With no options, just show the current settings.
        if all(option is None for option in (forum, controls, aviator_role)):
            forum_id = AirfieldRepository.get_config("forum_channel_id")
            controls_id = AirfieldRepository.get_config("controls_channel_id")
            aviator_id = AirfieldRepository.get_config(AIRFIELD_AVIATOR_ROLE_KEY)
            await ctx.send(
                "**Airfield settings**\n"
                f"Forum: {f'<#{forum_id}>' if forum_id else 'not set'}\n"
                f"Controls channel: {f'<#{controls_id}>' if controls_id else 'not set'}\n"
                f"Aviator role: {f'<@&{aviator_id}>' if aviator_id else 'not set (admins only)'}\n"
                f"Active war: **War {settings.get_active_war()}** (change it with `/scum config`)",
                ephemeral=True,
                allowed_mentions=no_pings
            )
            return

        await ctx.defer(ephemeral=True)
        changes = []

        if forum is not None:
            AirfieldRepository.set_config("forum_channel_id", str(forum.id))
            changes.append(f"Forum set to {forum.mention}.")

        if aviator_role is not None:
            AirfieldRepository.set_config(AIRFIELD_AVIATOR_ROLE_KEY, str(aviator_role.id))
            changes.append(f"Aviator role set to {aviator_role.mention}.")

        # Post (or move) the permanent controls message.
        if controls is not None:
            result = await refresh_control_panel(ctx.guild, channel=controls)
            if result == "failed":
                changes.append(
                    f"Couldn't post the controls message in {controls.mention}. "
                    "Check that the bot can view the channel, send messages and embed links there."
                )
            else:
                changes.append(f"Controls message {result} in {controls.mention}.")

        await ctx.send("\n".join(changes), ephemeral=True, allowed_mentions=no_pings)