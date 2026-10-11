import logging
import discord
from discord import ui
from app.core import settings
from app.core.ui import PASSCODE_PATTERN, BaseModal
from app.features.airfield.repository import AirfieldRepository
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
        code = self.airfield_id.value.strip()
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


class StructuredKillModal(BaseModal, title="Sortie Kill Sheet"):
    toxot_kills = ui.TextInput(label="Toxot-902 “Blind Silver” Kills (Fighter)", placeholder="0", default="0", required=False, max_length=2)
    harpy_kills = ui.TextInput(label="Daimon aK-5 “Harpy” Kills (Heavy Fighter)", placeholder="0", default="0", required=False, max_length=2)
    db_kills = ui.TextInput(label="Mergo-4 “Myrmidon” Kills (Dive Bomber)", placeholder="0", default="0", required=False, max_length=2)
    para_kills = ui.TextInput(label="V-5b Pegasus Kills (Paratrooper Plane)", placeholder="0", default="0", required=False, max_length=2)
    hb_kills = ui.TextInput(label="Tzykalia Kills (Heavy Bomber)", placeholder="0", default="0", required=False, max_length=2)
    notes = ui.TextInput(label="Additional Notes", placeholder="e.g. 1x Gunboat, Watchtowers", required=False, style=discord.TextStyle.paragraph)

    def __init__(self, plane_type: str, status: str):
        super().__init__()
        self.plane_type = str(plane_type) if plane_type else "Aircraft"
        self.status = str(status) if status else "Returned"

    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)

        def count(field: ui.TextInput) -> int:
            try:
                return max(0, int(field.value.strip() or "0"))
            except ValueError:
                return 0

        t_count = count(self.toxot_kills)
        h_count = count(self.harpy_kills)
        db_count = count(self.db_kills)
        para_count = count(self.para_kills)
        hb_count = count(self.hb_kills)

        total_air_kills = t_count + h_count + db_count + para_count + hb_count

        air_parts = []
        if t_count > 0: air_parts.append(f"{t_count}x Toxot-902")
        if h_count > 0: air_parts.append(f"{h_count}x Harpy")
        if db_count > 0: air_parts.append(f"{db_count}x Myrmidon")
        if para_count > 0: air_parts.append(f"{para_count}x Pegasus")
        if hb_count > 0: air_parts.append(f"{hb_count}x Tzykalia")

        air_summary = ", ".join(air_parts) if air_parts else "None"
        extra_notes = self.notes.value.strip()

        target_summary = f"Air: [{air_summary}]" + (f" | Notes: {extra_notes}" if extra_notes else "")

        completed = AirfieldRepository.complete_flight(user_id, self.status, total_air_kills, target_summary)

        if not completed:
            await interaction.send("You do not have an active flight to log.")
            return

        outcome = "returned" if self.status == "Returned" else "lost"
        await interaction.send(
            f"Flight logged: **{self.plane_type}** {outcome}.\n"
            f"Air kills: **{air_summary}**\n"
            f"Notes: {extra_notes or 'None'}"
        )

        kills_text = join_natural(air_parts)
        plane = f"{article(self.plane_type)} **{self.plane_type}**"
        if self.status == "Returned":
            log_msg = f"🛬 {interaction.user.mention} has returned {plane} to the stockpile"
            log_msg += f", taking down {kills_text}." if kills_text else "."
        else:
            log_msg = f"💥 {interaction.user.mention} has marked {plane} as lost"
            log_msg += f", taking down {kills_text} in the process." if kills_text else "."
        if extra_notes:
            log_msg += f"\nNotes: *{extra_notes}*"
        await log_to_depot_thread(interaction.guild, completed["airfield_id"], log_msg)