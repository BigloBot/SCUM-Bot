import discord
from discord import ui
from app.libs.discord.responses import Responder
from app.libs.discord.threads import create_recorded_thread
from app.core import settings
from app.libs.modals import BaseModal, FacilityModal
from app.features.airfield.dashboard import refresh_controls
from app.features.airfield.repository import DEFAULT_STOCK_SOURCE, AirfieldRepository
from app.features.airfield.service import format_depot_thread_title, log_depot_event
from app.features.airfield.views.depot.flight import (
    checkout_and_log,
    finish_flight,
)

class CreateDepotModal(FacilityModal, title="Create Airfield Depot"):
    noun = "depot"
    name_label = "Depot Name"
    name_placeholder = "e.g. ER-SCUM-AIR"
    location_label = "Region / Location"

    def is_duplicate(self, name: str) -> bool:
        return AirfieldRepository.check_duplicate(name)

    async def create(self, interaction: discord.Interaction, name: str, code: str, location: str):
        war_number = settings.get_active_war()
        content = (
            f"🏗️ {interaction.user.mention} has created this depot.\n"
            f"War: **{war_number}**\nName: **{name}**\nCode: **{code.upper()}**\nLocation: **{location}**"
        )
        # The thread is deleted again if the depot can't be saved, so none is left behind.
        await create_recorded_thread(
            interaction.guild,
            AirfieldRepository.get_config("forum_channel_id"),
            format_depot_thread_title(war_number, name, location),
            lambda thread: AirfieldRepository.add_airfield(name, code, location, str(thread.id) if thread else None),
            content,
        )
        await Responder(interaction).send(f"Depot **{name}** created. Location: **{location}**.")
        await refresh_controls(interaction.guild)


def stock_added_text(plane_type: str, source: str, qty: int) -> str:
    return f"**{qty}x {plane_type}** ({source.lower()})"


def add_stock(airfield_id: int, plane_type: str, user_id: str, source: str, qty: int) -> bool:
    """Adds `qty` aircraft to a depot's stock. False if the depot is no longer active in the current war."""
    for _ in range(qty):
        if not AirfieldRepository.add_plane(airfield_id, plane_type, user_id, source):
            return False
    return True


async def log_stock_added(interaction: discord.Interaction, airfield_id: int, plane_type: str, source: str, qty: int):
    """Posts the stock addition in the depot thread and refreshes the control panel. Call after replying."""
    await log_depot_event(
        interaction.guild,
        airfield_id,
        f"📦 {interaction.user.mention} has added {stock_added_text(plane_type, source, qty)} to the stockpile."
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
            await Responder(interaction).send("Tell us how you died so the loss can be logged. Press Loss to try again.")
            return
        await finish_flight(interaction, "Loss", cause=cause)
