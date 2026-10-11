import logging
import discord
from discord import ui
from app.core import settings
from app.core.ui import PASSCODE_PATTERN, BaseModal
from app.features.airfield.repository import AirfieldRepository
from app.features.airfield.panel import refresh_kill_board
from app.features.airfield.service import format_depot_thread_title
from app.features.airfield.views.utils import (
    article,
    checkout_and_log,
    join_natural,
    log_to_depot_thread,
)

logger = logging.getLogger(__name__)

class CreateDepotModal(BaseModal, title="Create Airfield Depot"):
    depot_name = ui.TextInput(label="Depot Name", placeholder="e.g. ER-SCUM-AIR", required=True, max_length=40)
    depot_code = ui.TextInput(label="Passcode (6 digits)", placeholder="e.g. 123456", required=True, min_length=6, max_length=6)
    depot_location = ui.TextInput(label="Region / Location", placeholder="e.g. Callahan's Passage", required=True, max_length=40)

    async def on_submit(self, interaction: discord.Interaction):
        name = self.depot_name.value.strip()
        code = self.depot_code.value.strip()
        location = self.depot_location.value.strip()

        if not name or not location:
            await interaction.send("The depot name and location can't be empty.")
            return
        if not PASSCODE_PATTERN.fullmatch(code):
            await interaction.send("The passcode must be exactly 6 digits (0-9).")
            return

        if AirfieldRepository.check_duplicate(name):
            await interaction.send("A depot with that name is already active in this war.")
            return

        await interaction.response.defer(ephemeral=True)

        war_number = settings.get_active_war()
        forum_channel_id = AirfieldRepository.get_config("forum_channel_id")
        thread = None
        if forum_channel_id:
            forum = interaction.guild.get_channel(int(forum_channel_id))
            if isinstance(forum, discord.ForumChannel):
                try:
                    thread_content = (
                        f"🏗️ {interaction.user.mention} has created this depot.\n"
                        f"War: **{war_number}**\nName: **{name}**\nCode: **{code.upper()}**\nLocation: **{location}**"
                    )
                    created_thread = await forum.create_thread(
                        name=format_depot_thread_title(war_number, name, location),
                        content=thread_content,
                        allowed_mentions=discord.AllowedMentions.none()
                    )
                    thread = created_thread.thread
                except Exception as e:
                    logger.error(f"Error creating forum thread: {e}")

        AirfieldRepository.add_airfield(name, code, location, str(thread.id) if thread else None)
        await interaction.send(f"Depot **{name}** created. Location: **{location}**.")


class AddStockModal(BaseModal, title="Add Aircraft Stock"):
    quantity = ui.TextInput(label="Quantity", placeholder="1", default="1", required=True, max_length=3)

    def __init__(self, airfield_id: int, plane_type: str):
        super().__init__(title=f"Add {plane_type}"[:45])
        self.airfield_id = airfield_id
        self.plane_type = plane_type

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = int(self.quantity.value.strip())
            if qty <= 0:
                raise ValueError()
        except ValueError:
            await interaction.send("Please enter a valid positive number for the quantity.")
            return

        plane = self.plane_type
        user_id = str(interaction.user.id)

        for _ in range(qty):
            if not AirfieldRepository.add_plane(self.airfield_id, plane, user_id):
                await interaction.send("That depot is no longer active in the current war.")
                return

        await interaction.send(f"Added **{qty}x {plane}** to the stockpile.")
        await log_to_depot_thread(
            interaction.guild,
            self.airfield_id,
            f"📦 {interaction.user.mention} has added **{qty}x {plane}** to the stockpile."
        )


class CustomMissionModal(BaseModal, title="Check Out Aircraft - Custom Mission"):
    usecase = ui.TextInput(label="Flight Purpose / Operation Details", placeholder="Describe custom operation...", required=True, style=discord.TextStyle.paragraph)

    def __init__(self, airfield_id: int, plane_type: str):
        super().__init__()
        self.airfield_id = airfield_id
        self.plane_type = plane_type

    async def on_submit(self, interaction: discord.Interaction):
        await checkout_and_log(interaction, self.airfield_id, self.plane_type, self.usecase.value.strip())


class KillReportModal(BaseModal, title="Report Kills"):
    """Kills are reported on their own, separately from logging a flight's return."""
    toxot_kills = ui.TextInput(label="Toxot-902 “Blind Silver” Kills (Fighter)", placeholder="0", default="0", required=False, max_length=3)
    harpy_kills = ui.TextInput(label="Daimon aK-5 “Harpy” Kills (Heavy Fighter)", placeholder="0", default="0", required=False, max_length=3)
    db_kills = ui.TextInput(label="Mergo-4 “Myrmidon” Kills (Dive Bomber)", placeholder="0", default="0", required=False, max_length=3)
    para_kills = ui.TextInput(label="V-5b Pegasus Kills (Paratrooper Plane)", placeholder="0", default="0", required=False, max_length=3)
    hb_kills = ui.TextInput(label="Tzykalia Kills (Heavy Bomber)", placeholder="0", default="0", required=False, max_length=3)

    async def on_submit(self, interaction: discord.Interaction):
        def count(field: ui.TextInput) -> int:
            try:
                return max(0, int(field.value.strip() or "0"))
            except ValueError:
                return 0

        by_type = {
            "toxot": count(self.toxot_kills), "harpy": count(self.harpy_kills), "myrmidon": count(self.db_kills),
            "pegasus": count(self.para_kills), "tzykalia": count(self.hb_kills),
        }
        names = {"toxot": "Toxot-902", "harpy": "Harpy", "myrmidon": "Myrmidon", "pegasus": "Pegasus", "tzykalia": "Tzykalia"}
        parts = [f"{n}x {names[k]}" for k, n in by_type.items() if n > 0]
        if not parts:
            await interaction.send("No kills entered, so nothing was recorded.")
            return

        AirfieldRepository.add_kill_report(str(interaction.user.id), by_type)
        await interaction.send(f"Kills recorded: **{join_natural(parts)}**.")
        await refresh_kill_board(interaction.guild)
