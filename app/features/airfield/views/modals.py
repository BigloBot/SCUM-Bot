import logging
import discord
from discord import ui
from app.core import settings
from app.libs.modals import BaseModal, FacilityModal
from app.features.airfield.dashboard import refresh_controls
from app.features.airfield.repository import AirfieldRepository
from app.features.airfield.service import format_depot_thread_title
from app.features.airfield.views.utils import (
    checkout_and_log,
    finish_flight,
    log_to_depot_thread,
)

logger = logging.getLogger(__name__)

class CreateDepotModal(FacilityModal, title="Create Airfield Depot"):
    noun = "depot"
    name_label = "Depot Name"
    name_placeholder = "e.g. ER-SCUM-AIR"
    location_label = "Region / Location"

    def is_duplicate(self, name: str) -> bool:
        return AirfieldRepository.check_duplicate(name)

    async def create(self, interaction: discord.Interaction, name: str, code: str, location: str):
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
        await refresh_controls(interaction.guild)


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
        await refresh_controls(interaction.guild)


class CustomMissionModal(BaseModal, title="Check Out Aircraft - Custom Mission"):
    usecase = ui.TextInput(label="Flight Purpose / Operation Details", placeholder="Describe custom operation...", required=True, style=discord.TextStyle.paragraph)

    def __init__(self, airfield_id: int, plane_type: str):
        super().__init__()
        self.airfield_id = airfield_id
        self.plane_type = plane_type

    async def on_submit(self, interaction: discord.Interaction):
        await checkout_and_log(interaction, self.airfield_id, self.plane_type, self.usecase.value.strip())


MAX_CAUSE_LENGTH = 300


class LossCauseModal(BaseModal, title="Log Loss"):
    """Asked when a pilot reports losing their aircraft: how they died, which goes into the depot thread log."""
    def __init__(self):
        super().__init__()
        self.cause = ui.TextInput(
            label="How did you die?",
            placeholder="e.g. Shot down by a Toxot over Callahan's Passage",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=MAX_CAUSE_LENGTH,
        )
        self.add_item(self.cause)

    async def on_submit(self, interaction: discord.Interaction):
        cause = self.cause.value.strip()
        if not cause:
            await interaction.send("Tell us how you died so the loss can be logged. Press Loss to try again.")
            return
        await finish_flight(interaction, "Loss", cause=cause)
