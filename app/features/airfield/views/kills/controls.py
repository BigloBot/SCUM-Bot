"""Persistent controls attached to the airfield kill board."""
import discord
from discord import ui

from app.features.airfield.permissions import can_use_airfield
from app.features.airfield.views.kills.admin import open_kill_fix
from app.features.airfield.views.kills.reporting import open_kill_report
from app.libs.views.views import BaseView


class KillBoardView(BaseView):
    """Persistent actions for reporting and correcting kill-board entries."""

    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if can_use_airfield(interaction.user):
            return True
        await interaction.send("You don't have permission to use these controls.")
        return False

    @ui.button(label="Report Kills", style=discord.ButtonStyle.secondary, custom_id="scum:report_kills")
    async def report_kills(self, interaction: discord.Interaction, button: ui.Button):
        await open_kill_report(interaction)

    @ui.button(label="Fix Kills", style=discord.ButtonStyle.secondary, custom_id="scum:fix_kills")
    async def fix_kills(self, interaction: discord.Interaction, button: ui.Button):
        await open_kill_fix(interaction)
