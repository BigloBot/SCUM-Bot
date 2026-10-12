import re
import logging
import discord
from discord import ui
from app.core import settings
from app.core.ui import PASSCODE_PATTERN, BaseModal, BaseView
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


MAX_MODAL_FIELDS = 5  # Discord allows at most five inputs in one form
MEDIA_URL_PATTERN = re.compile(r"https?://[^\s<>]+")


class KillReportModal(BaseModal):
    """One count field per kill type, built from the kill_types list. Kills are reported separately from flights."""

    def __init__(self, kill_types):
        super().__init__(title="Report Kills")
        self.fields_by_type: dict[int, ui.TextInput] = {}
        self.labels_by_type: dict[int, str] = {}
        for kill_type in list(kill_types)[:MAX_MODAL_FIELDS]:
            field = ui.TextInput(
                label=kill_type["modal_label"][:45], placeholder="0", default="0", required=False, max_length=3
            )
            self.add_item(field)
            self.fields_by_type[kill_type["id"]] = field
            self.labels_by_type[kill_type["id"]] = kill_type["label"]

    async def on_submit(self, interaction: discord.Interaction):
        counts = {}
        for type_id, field in self.fields_by_type.items():
            try:
                counts[type_id] = max(0, int(field.value.strip() or "0"))
            except ValueError:
                counts[type_id] = 0

        report_id = AirfieldRepository.add_kill_report(str(interaction.user.id), counts)
        if report_id is None:
            await interaction.send("No kills entered, so nothing was recorded.")
            return

        parts = [f"{n}x {self.labels_by_type[type_id]}" for type_id, n in counts.items() if n > 0]
        await interaction.send(
            f"Kills recorded: **{join_natural(parts)}**.\n"
            "Got a photo or clip? Add a link to show it on the kill board.",
            view=KillMediaView(report_id),
            delete_after=180
        )
        await refresh_kill_board(interaction.guild)


class KillMediaView(BaseView):
    """Offered after a kill report so the pilot can attach a photo or clip link to it."""
    def __init__(self, report_id: int):
        super().__init__(timeout=180)
        self.report_id = report_id

    @ui.button(label="Add photo / clip link", style=discord.ButtonStyle.secondary, emoji="🎬")
    async def add_media(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(KillMediaModal(self.report_id))


class KillMediaModal(BaseModal, title="Photo / Clip Link"):
    media_url = ui.TextInput(
        label="Link to your photo or clip", placeholder="https://...", required=True, max_length=500
    )

    def __init__(self, report_id: int):
        super().__init__()
        self.report_id = report_id

    async def on_submit(self, interaction: discord.Interaction):
        url = self.media_url.value.strip()
        if not MEDIA_URL_PATTERN.fullmatch(url):
            await interaction.send("That doesn't look like a link. It needs to start with http:// or https://.")
            return
        if not AirfieldRepository.set_kill_report_media(self.report_id, str(interaction.user.id), url):
            await interaction.send("That kill report can't be updated.")
            return
        await interaction.send("Link added to your kill report.")
        await refresh_kill_board(interaction.guild)
