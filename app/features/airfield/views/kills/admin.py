"""Admin correction of the kill board: pick a pilot, pick one of their reports, then change its count or delete it."""
import logging
import discord
from discord import ui
from app.core.permissions import is_admin
from app.core.config import config
from app.features.airfield.dashboard import refresh_kill_board
from app.features.airfield.repository import AirfieldRepository
from app.libs.modals import BaseModal
from app.libs.views.views import BaseView

logger = logging.getLogger(__name__)

MAX_KILL_COUNT = 999  # the correction form allows three digits


def _type_label(kill_type: str) -> str:
    return config.features.airfield.kill_type_label(kill_type)


def _entry_label(entry) -> str:
    return f"{entry['count']}x {_type_label(entry['kill_type'])} - {entry['created_at'][:16]} UTC"


class EditKillCountModal(BaseModal, title="Correct Kill Count"):
    def __init__(self, user_id: str, report_id: int, kill_type: str, current: int):
        super().__init__()
        self.new_count = ui.TextInput(
            label="New number of kills", default=str(current), required=True, min_length=1, max_length=3)
        self.add_item(self.new_count)
        self.user_id = user_id
        self.report_id = report_id
        self.kill_type = kill_type

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.new_count.value.strip()
        if not raw.isascii() or not raw.isdigit() or not 1 <= int(raw) <= MAX_KILL_COUNT:
            await interaction.send(f"Enter a whole number from 1 to {MAX_KILL_COUNT}. To remove the report, delete it instead.")
            return
        if not AirfieldRepository.set_kill_entry_count(self.report_id, self.kill_type, int(raw)):
            await interaction.send("That kill report no longer exists.")
            return
        logger.info("%s set kill report %s (%s, pilot %s) to %s", interaction.user.id, self.report_id, self.kill_type, self.user_id, raw)
        await interaction.send(f"Updated to **{raw}x {_type_label(self.kill_type)}** for <@{self.user_id}>.")
        await refresh_kill_board(interaction.guild)


class KillEntryActionView(BaseView):
    """Shown for one chosen report: change its count or delete it."""
    def __init__(self, user_id: str, report_id: int, kill_type: str, current: int):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.report_id = report_id
        self.kill_type = kill_type
        self.current = current

    @ui.button(label="Change count", style=discord.ButtonStyle.primary)
    async def change(self, interaction: discord.Interaction, button: ui.Button):
        if not is_admin(interaction.user):
            await interaction.send("Only admins can correct kill reports.")
            return
        await interaction.response.send_modal(EditKillCountModal(self.user_id, self.report_id, self.kill_type, self.current))

    @ui.button(label="Delete report", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: ui.Button):
        if not is_admin(interaction.user):
            await interaction.send("Only admins can correct kill reports.")
            return
        if not AirfieldRepository.delete_kill_entry(self.report_id, self.kill_type):
            await interaction.send("That kill report no longer exists.")
            return
        logger.info("%s deleted kill report %s (%s, pilot %s)", interaction.user.id, self.report_id, self.kill_type, self.user_id)
        await interaction.send(f"Deleted **{self.current}x {_type_label(self.kill_type)}** from <@{self.user_id}>'s reports.")
        await refresh_kill_board(interaction.guild)


class KillEntrySelect(ui.Select):
    def __init__(self, user_id: str, entries):
        self.user_id = user_id
        self.entries = {f"{e['report_id']}:{e['kill_type']}": e for e in entries}
        options = [
            discord.SelectOption(label=_entry_label(e)[:100], value=key)
            for key, e in self.entries.items()
        ]
        super().__init__(placeholder="Choose the report to correct...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        entry = self.entries[self.values[0]]
        view = KillEntryActionView(self.user_id, entry["report_id"], entry["kill_type"], entry["count"])
        await interaction.send(f"<@{self.user_id}>: **{_entry_label(entry)}**. What should happen to it?", view=view)


class KillPilotSelect(ui.UserSelect):
    def __init__(self):
        super().__init__(placeholder="Choose the pilot...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        pilot = self.values[0]
        entries = AirfieldRepository.get_pilot_kill_entries(str(pilot.id))
        if not entries:
            await interaction.send(f"{pilot.mention} has no kill reports in the active war.")
            return
        view = BaseView(timeout=180)
        view.add_item(KillEntrySelect(str(pilot.id), entries))
        await interaction.send(f"{pilot.mention}'s latest kill reports (active war):", view=view)


async def open_kill_fix(interaction: discord.Interaction):
    """Admins only: starts correcting a pilot's kill reports."""
    if not is_admin(interaction.user):
        await interaction.send("Only admins can correct kill reports.")
        return
    view = BaseView(timeout=180)
    view.add_item(KillPilotSelect())
    await interaction.send("Whose kill report needs correcting?", view=view)
