"""Bank: officer stockpiles and rare materials. Plugs into the bot through `feature`."""
from typing import Optional

import discord
from discord import app_commands

from app.core import settings
from app.core.permissions import has_admin
from app.features.bank.board import BANK_CHANNEL_KEY, rebuild_board, sync_stockpile_board
from app.features.bank.permissions import BANK_OFFICER_ROLE_KEY
from app.libs.discord.format import channel_or, panel_posted_line, role_or
from app.libs.discord.responses import Responder
from app.libs.feature import Feature, rebuild_on_war_change


def persistent_views():
    from app.features.bank.views import BankControlView
    return (BankControlView(),)


def register(scum: app_commands.Group) -> None:
    bank = app_commands.Group(name="bank", description="Officer stockpiles and rare materials.", parent=scum)

    @bank.command(name="config", description="View or change bank settings (admins only).")
    @app_commands.describe(
        channel="Channel for the bank control panel and stockpile board. Run again to rebuild it.",
        officer_role="Role allowed to use the bank controls.",
    )
    @has_admin()
    async def config(
            interaction: discord.Interaction,
            channel: Optional[discord.TextChannel] = None,
            officer_role: Optional[discord.Role] = None,
    ):
        reply = Responder(interaction)

        # With no options, just show the current settings.
        if channel is None and officer_role is None:
            await reply.send(
                "**Bank settings**\n"
                f"Channel: {channel_or(settings.get_setting(BANK_CHANNEL_KEY))}\n"
                f"Officer role: {role_or(settings.get_setting(BANK_OFFICER_ROLE_KEY))}\n"
                f"Active war: **War {settings.get_active_war()}** (change it with `/scum config`)"
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        changes = []

        if officer_role is not None:
            settings.set_setting(BANK_OFFICER_ROLE_KEY, str(officer_role.id))
            changes.append(f"Bank officer role set to {officer_role.mention}.")

        # Posting a channel (re)builds the whole board: control panel first, then the stockpile board.
        if channel is not None:
            result = await rebuild_board(interaction.guild, channel)
            changes.append(panel_posted_line(result, channel, "bank board"))

        await reply.send("\n".join(changes))


feature = Feature(
    name="Bank",
    help="officer stockpiles and rare materials. Use the controls panel; `/scum bank config` sets it up.",
    register=register,
    persistent_views=persistent_views,
    resync=sync_stockpile_board,
    # Switching war shows only that war's stockpiles, so the board is rebuilt.
    on_war_change=rebuild_on_war_change(rebuild_board, "bank board"),
)
