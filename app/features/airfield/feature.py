"""Airfield: depots, flights, kills and stats. Plugs into the bot through `feature`."""
from typing import Literal, Optional

import discord
from discord import app_commands

from app.core import settings
from app.core.permissions import has_admin
from app.features.airfield.dashboard import (
    CONTROLS_CHANNEL_KEY, rebuild_dashboard, refresh_controls, resync_dashboard,
)
from app.features.airfield.permissions import AIRFIELD_AVIATOR_ROLE_KEY, can_use_airfield
from app.features.airfield.repository import AirfieldRepository
from app.features.airfield.service import sync_war_threads
from app.features.airfield.stats import build_production_embed, build_stats_embed
from app.libs.discord.format import channel_or, panel_posted_line, role_or
from app.libs.discord.responses import Responder
from app.libs.feature import Feature

STATS_VISIBLE_SECONDS = 120  # how long the stats reply stays up before it deletes itself
FORUM_CHANNEL_KEY = "forum_channel_id"


def persistent_views():
    # Imported here so the views (which import the dashboard) don't make a cycle with this module.
    from app.features.airfield.views.depot.controls import DepotManagementView
    from app.features.airfield.views.kills.controls import KillBoardView
    return DepotManagementView(), KillBoardView()


async def on_war_change(guild: discord.Guild, war: int) -> list[str]:
    """Brings every depot thread in line with the new war, and the war shown on the controls."""
    # Switching back to an earlier war reopens exactly that war's threads and locks all the others.
    counts = await sync_war_threads(guild, war)
    lines = [f"Depot threads synced: {counts['changed']} updated, {counts['unchanged']} already correct."]
    if counts["failed"]:
        lines.append(f"{counts['failed']} could not be updated (check the bot's Manage Threads permission).")
    if counts["missing"]:
        lines.append(f"{counts['missing']} no longer exist in Discord.")
    await refresh_controls(guild)
    return lines


def register(scum: app_commands.Group) -> None:
    # Pilot actions all have a button on the permanent controls message; only stats and settings are commands.
    # Everything lives under /scum airfield. Discord only applies command visibility to top-level
    # commands, so /scum stays visible to everyone and permissions are enforced when a command runs.
    airfield = app_commands.Group(
        name="airfield", description="Airfield depots, stockpiles and flights.", parent=scum
    )

    @airfield.command(name="stats", description="Top aces, busiest pilots and aircraft production for a war.")
    @app_commands.describe(
        war="War to show (defaults to the active war).",
        source="Only count aircraft added to stock from this source (Produced, Purchased or Other).",
    )
    async def stats(
            interaction: discord.Interaction,
            war: Optional[int] = None,
            source: Optional[Literal["Produced", "Purchased", "Other"]] = None,
    ):
        reply = Responder(interaction)
        if not can_use_airfield(interaction.user):
            await reply.send("You don't have permission to use airfield commands.")
            return
        war = war if war is not None else settings.get_active_war()
        embeds = [
            build_stats_embed(war, AirfieldRepository.get_pilot_stats(war)),
            build_production_embed(
                war, AirfieldRepository.get_production_stats(war, source=source),
                AirfieldRepository.get_aircraft_types(), settings.get_active_war()
            ),
        ]
        # Private reply that deletes itself, like the other airfield replies (two embeds take a while to read).
        await reply.send(embeds=embeds, delete_after=STATS_VISIBLE_SECONDS)

    @airfield.command(name="config", description="View or change airfield settings (admins only).")
    @app_commands.describe(
        forum="Forum channel where depot threads are created.",
        controls="Channel that holds the permanent control panel message.",
        aviator_role="Role allowed to use the airfield controls.",
    )
    @has_admin()
    async def config(
            interaction: discord.Interaction,
            forum: Optional[discord.ForumChannel] = None,
            controls: Optional[discord.TextChannel] = None,
            aviator_role: Optional[discord.Role] = None,
    ):
        reply = Responder(interaction)

        # With no options, just show the current settings.
        if forum is None and controls is None and aviator_role is None:
            await reply.send(
                "**Airfield settings**\n"
                f"Forum: {channel_or(AirfieldRepository.get_config(FORUM_CHANNEL_KEY))}\n"
                f"Controls channel: {channel_or(settings.get_setting(CONTROLS_CHANNEL_KEY))}\n"
                f"Aviator role: {role_or(AirfieldRepository.get_config(AIRFIELD_AVIATOR_ROLE_KEY))}\n"
                f"Active war: **War {settings.get_active_war()}** (change it with `/scum config`)"
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        changes = []

        if forum is not None:
            AirfieldRepository.set_config(FORUM_CHANNEL_KEY, str(forum.id))
            changes.append(f"Forum set to {forum.mention}.")

        if aviator_role is not None:
            AirfieldRepository.set_config(AIRFIELD_AVIATOR_ROLE_KEY, str(aviator_role.id))
            changes.append(f"Aviator role set to {aviator_role.mention}.")

        # Post (or move) the permanent controls message, with the kill board under it.
        if controls is not None:
            result = await rebuild_dashboard(interaction.guild, controls)
            changes.append(panel_posted_line(result, controls, "controls message"))

        await reply.send("\n".join(changes))


feature = Feature(
    name="Airfield",
    help="depots, flights, kills and stats. Use the controls panel; `/scum airfield stats` and `config` for the rest.",
    register=register,
    persistent_views=persistent_views,
    resync=resync_dashboard,
    on_war_change=on_war_change,
)
