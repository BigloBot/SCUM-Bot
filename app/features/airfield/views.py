import logging
import traceback
import discord
from discord import ui
from app.features.airfield.repository import AirfieldRepository

logger = logging.getLogger(__name__)

# Official Warden Aircraft List
STANDARD_AIRCRAFT = [
    "Harbinger (Fighter)",
    "Welkinrive (Heavy Bomber)",
    "Austringer (Torpedo Bomber)",
    "Zealot (Paratrooper Transport)",
    "White Raven (SeaFighter)"
]

# Standard mission presets
MISSION_PRESETS = [
    "Large Ship Escort",
    "Heavy Bomber Escort",
    "Paratrooper Deployment",
    "Transport",
    "QRF",
    "Other"
]

# Helper function to auto-log flight events in forum threads
async def log_to_depot_thread(guild: discord.Guild, depot_code: str, message: str, war_number: int = None):
    depot = AirfieldRepository.get_depot(depot_code, war_number)
    if depot and depot["thread_id"]:
        try:
            thread = guild.get_channel(int(depot["thread_id"]))
            if thread:
                await thread.send(message)
        except Exception as e:
            logger.error(f"Failed to send log to thread {depot['thread_id']}: {e}")

# ==================== DEPOT MODALS ====================

class CreateDepotModal(ui.Modal, title="Create Airfield Depot"):
    depot_name = ui.TextInput(label="Depot Name", placeholder="e.g. Warden Alpha", required=True)
    depot_code = ui.TextInput(label="Passcode / Code", placeholder="e.g. W-ALPHA", required=True, max_length=10)
    depot_location = ui.TextInput(label="Region / Location", placeholder="e.g. Callahan's Passage", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        name = self.depot_name.value.strip()
        code = self.depot_code.value.strip()
        location = self.depot_location.value.strip()

        duplicate = AirfieldRepository.check_duplicate(name, code)
        if duplicate:
            await interaction.response.send_message(
                f"❌ A depot with that {'name' if duplicate == 'name' else 'code'} already exists in this war!",
                ephemeral=True
            )
            return

        forum_channel_id = AirfieldRepository.get_config("forum_channel_id")
        thread = None
        if forum_channel_id:
            forum = interaction.guild.get_channel(int(forum_channel_id))
            if isinstance(forum, discord.ForumChannel):
                try:
                    thread_content = f"🛡️ **Depot Created**\nName: **{name}**\nLocation: **{location}**"
                    created_thread = await forum.create_thread(
                        name=f"[{code.upper()}] {name}",
                        content=thread_content
                    )
                    thread = created_thread.thread
                except Exception as e:
                    logger.error(f"Error creating forum thread: {e}")

        AirfieldRepository.add_airfield(name, code, location, str(thread.id) if thread else None)
        await interaction.response.send_message(f"✅ Airfield depot **{name}** created successfully!\nLocation: **{location}**", ephemeral=True)


class AddStockModal(ui.Modal, title="Add Aircraft Stock"):
    plane_type = ui.TextInput(label="Aircraft Type", placeholder="e.g. Harbinger (Fighter)", required=True)
    quantity = ui.TextInput(label="Quantity", placeholder="1", default="1", required=True, max_length=3)

    def __init__(self, depot_code: str):
        super().__init__()
        self.depot_code = depot_code

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = int(self.quantity.value.strip())
            if qty <= 0:
                raise ValueError()
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid positive number for quantity.", ephemeral=True)
            return

        plane = self.plane_type.value.strip()
        user_id = str(interaction.user.id)

        for _ in range(qty):
            AirfieldRepository.add_plane(self.depot_code, plane, user_id)

        await interaction.response.send_message(f"✅ Added **{qty}x {plane}** to depot.", ephemeral=True)
        await log_to_depot_thread(
            interaction.guild,
            self.depot_code,
            f"📦 **Stock Added:** {interaction.user.mention} added **{qty}x {plane}** to stockpile."
        )


class CustomMissionModal(ui.Modal, title="Check Out Aircraft - Custom Mission"):
    usecase = ui.TextInput(label="Flight Purpose / Operation Details", placeholder="Describe custom operation...", required=True, style=discord.TextStyle.paragraph)

    def __init__(self, depot_code: str, plane_type: str):
        super().__init__()
        self.depot_code = depot_code
        self.plane_type = plane_type

    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        mission = self.usecase.value.strip()
        success = AirfieldRepository.checkout_plane(self.depot_code, self.plane_type, mission, user_id)
        if not success:
            await interaction.response.send_message("⚠️ You already have an active flight checked out! Please complete your return log first (`/airfield log return`).", ephemeral=True)
            return

        depot = AirfieldRepository.get_depot(self.depot_code)
        location = depot["location"] if depot else "Unknown Location"
        await interaction.response.send_message(
            f"✈️ Successfully checked out **{self.plane_type}**!\n"
            f"Mission: **{mission}**\n"
            f"Location: **{location}**\n"
            f"Good hunting, aviator!",
            ephemeral=True
        )
        await log_to_depot_thread(
            interaction.guild,
            self.depot_code,
            f"✈️ **Aircraft Departure:** {interaction.user.mention} checked out a **{self.plane_type}**.\nMission: *{mission}*"
        )


# ==================== STEP 2: FLIGHT RETURN KILL SHEET MODAL ====================

class StructuredKillModal(ui.Modal, title="Sortie Kill Sheet"):
    toxot_kills = ui.TextInput(label="Toxot Kills", placeholder="0", default="0", required=False, max_length=3)
    harpy_kills = ui.TextInput(label="Harpy Kills", placeholder="0", default="0", required=False, max_length=3)
    peregrine_kills = ui.TextInput(label="Peregrine / Tzykalia Kills", placeholder="0", default="0", required=False, max_length=3)
    notes = ui.TextInput(label="Ground Targets / Operation Notes", placeholder="e.g. 1x Gunboat, Watchtowers", required=False, style=discord.TextStyle.paragraph)

    def __init__(self, plane_type: str, status: str):
        super().__init__()
        self.plane_type = str(plane_type) if plane_type else "Aircraft"
        self.status = str(status) if status else "Returned"

    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)

        try:
            t_count = int(self.toxot_kills.value.strip() or "0")
        except ValueError:
            t_count = 0
        try:
            h_count = int(self.harpy_kills.value.strip() or "0")
        except ValueError:
            h_count = 0
        try:
            p_count = int(self.peregrine_kills.value.strip() or "0")
        except ValueError:
            p_count = 0

        total_air_kills = t_count + h_count + p_count

        air_parts = []
        if t_count > 0: air_parts.append(f"{t_count}x Toxot")
        if h_count > 0: air_parts.append(f"{h_count}x Harpy")
        if p_count > 0: air_parts.append(f"{p_count}x Peregrine/Tzykalia")

        air_summary = ", ".join(air_parts) if air_parts else "None"
        extra_notes = self.notes.value.strip()

        target_summary = f"Air: [{air_summary}]" + (f" | Notes: {extra_notes}" if extra_notes else "")

        completed = AirfieldRepository.complete_flight(user_id, self.status, total_air_kills, target_summary)

        if not completed:
            await interaction.response.send_message("⚠️ You do not have an active flight to return.", ephemeral=True)
            return

        status_emoji = "🛬" if self.status == "Returned" else "💥"

        await interaction.response.send_message(
            f"✅ **Flight Return Logged!**\n"
            f"• Aircraft: **{self.plane_type}**\n"
            f"• Status: {status_emoji} **{self.status}**\n"
            f"• Confirmed Air Kills: **{air_summary}**\n"
            f"• Notes: {extra_notes or 'None'}",
            ephemeral=True
        )

        # Log return event in the depot thread
        if completed["airfield_code"]:
            log_msg = (
                f"{status_emoji} **Sortie Completed:** {interaction.user.mention} logged flight return.\n"
                f"• Aircraft: **{self.plane_type}**\n"
                f"• Status: **{self.status}**\n"
                f"• Air Kills: **{air_summary}**\n"
                f"• Notes: *{extra_notes or 'None'}*"
            )
            await log_to_depot_thread(interaction.guild, completed["airfield_code"], log_msg, completed["war_number"])

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.error(f"Exception in StructuredKillModal: {error}")
        traceback.print_exception(type(error), error, error.__traceback__)
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ An internal error occurred while submitting the kill sheet: `{error}`", ephemeral=True)


# ==================== STEP 1: FLIGHT RETURN BUTTONS ====================

class FlightReturnStatusView(ui.View):
    """Clean Step 1: Pilot clicks Returned or Loss to trigger Kill Sheet popup."""
    def __init__(self, flight):
        super().__init__(timeout=180)
        plane = "Aircraft"
        if flight:
            try:
                plane = flight["plane_type"]
            except Exception:
                plane = str(flight)
        self.plane_type = plane

    @ui.button(label="Returned", style=discord.ButtonStyle.green, emoji="🛬")
    async def returned(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(StructuredKillModal(self.plane_type, "Returned"))

    @ui.button(label="Loss", style=discord.ButtonStyle.danger, emoji="💥")
    async def loss(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(StructuredKillModal(self.plane_type, "Loss"))


# ==================== CHECKOUT MISSION SELECT ====================

class MissionSelect(ui.Select):
    def __init__(self, depot_code: str, plane_type: str):
        self.depot_code = depot_code
        self.plane_type = plane_type

        options = [discord.SelectOption(label=m) for m in MISSION_PRESETS]
        super().__init__(placeholder="Select mission / operation type...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        mission = self.values[0]
        if mission == "Other":
            await interaction.response.send_modal(CustomMissionModal(self.depot_code, self.plane_type))
        else:
            user_id = str(interaction.user.id)
            success = AirfieldRepository.checkout_plane(self.depot_code, self.plane_type, mission, user_id)
            if not success:
                await interaction.response.send_message("⚠️ You already have an active flight checked out! Please complete your return log first (`/airfield log return`).", ephemeral=True)
                return

            depot = AirfieldRepository.get_depot(self.depot_code)
            location = depot["location"] if depot else "Unknown Location"
            await interaction.response.send_message(
                f"✈️ Successfully checked out **{self.plane_type}**!\n"
                f"Mission: **{mission}**\n"
                f"Location: **{location}**\n"
                f"Good hunting, aviator!",
                ephemeral=True
            )
            await log_to_depot_thread(
                interaction.guild,
                self.depot_code,
                f"✈️ **Aircraft Departure:** {interaction.user.mention} checked out a **{self.plane_type}**.\nMission: *{mission}*"
            )


class MissionSelectView(ui.View):
    def __init__(self, depot_code: str, plane_type: str):
        super().__init__(timeout=180)
        self.add_item(MissionSelect(depot_code, plane_type))


# ==================== CHECKOUT AIRCRAFT SELECT ====================

class PlaneSelect(ui.Select):
    """Displays stock count subtext for each aircraft type."""
    def __init__(self, depot_code: str):
        self.depot_code = depot_code

        stock = {s["plane_type"]: s["count"] for s in AirfieldRepository.get_stock_summary(depot_code)}

        options = []
        for p in STANDARD_AIRCRAFT:
            count = stock.get(p, 0)
            if count > 0:
                desc = f"{count} in stockpile"
            else:
                desc = "None registered in stockpile"
            options.append(discord.SelectOption(label=p, description=desc))

        super().__init__(placeholder="Choose an aircraft type...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        plane_type = self.values[0]
        view = MissionSelectView(self.depot_code, plane_type)
        await interaction.response.send_message(f"Select mission purpose for **{plane_type}**:", view=view, ephemeral=True)


class PlaneSelectView(ui.View):
    def __init__(self, depot_code: str):
        super().__init__(timeout=180)
        self.add_item(PlaneSelect(depot_code))


# ==================== DEPOT SELECTS & CONTROL PANEL ====================

class DepotSelect(ui.Select):
    def __init__(self, action: str):
        self.action = action
        depots = AirfieldRepository.get_airfields()
        options = [
            discord.SelectOption(label=d["name"], value=d["code"], description=f"Location: {d['location']}")
            for d in depots[:25]
        ]
        if not options:
            options = [discord.SelectOption(label="No depots available", value="NONE")]
        super().__init__(placeholder="Choose an airfield depot...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "NONE":
            await interaction.response.send_message("❌ No depots available.", ephemeral=True)
            return

        code = self.values[0]
        if self.action == "add_stock":
            await interaction.response.send_modal(AddStockModal(code))
        elif self.action == "view_details":
            depot = AirfieldRepository.get_depot(code)
            stock = AirfieldRepository.get_stock_summary(code)
            stock_str = "\n".join([f"• **{s['plane_type']}**: {s['count']}" for s in stock]) or "No planes registered in stock."
            await interaction.response.send_message(
                f"🛡️ **Depot Details: {depot['name']}**\n"
                f"Location: **{depot['location']}**\n\n"
                f"**Stock Inventory:**\n{stock_str}",
                ephemeral=True
            )
        elif self.action == "delete":
            AirfieldRepository.delete_airfield(code)
            await interaction.response.send_message("🗑️ Depot has been deleted/archived.", ephemeral=True)
        elif self.action == "flight":
            view = PlaneSelectView(code)
            await interaction.response.send_message("Select the aircraft type you are taking out:", view=view, ephemeral=True)


class DepotManagementView(ui.View):
    def __init__(self, forum_channel: discord.ForumChannel):
        super().__init__(timeout=None)
        self.forum_channel = forum_channel

    @ui.button(label="Create Depot", style=discord.ButtonStyle.green, emoji="➕")
    async def create_depot(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(CreateDepotModal())

    @ui.button(label="Add Aircraft Stock", style=discord.ButtonStyle.primary, emoji="📦")
    async def add_stock(self, interaction: discord.Interaction, button: ui.Button):
        view = ui.View()
        view.add_item(DepotSelect("add_stock"))
        await interaction.response.send_message("Select the depot to add stock to:", view=view, ephemeral=True)

    @ui.button(label="View Depots", style=discord.ButtonStyle.secondary, emoji="🔍")
    async def view_depots(self, interaction: discord.Interaction, button: ui.Button):
        view = ui.View()
        view.add_item(DepotSelect("view_details"))
        await interaction.response.send_message("Select the depot to view:", view=view, ephemeral=True)

    @ui.button(label="Delete Depot", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_depot(self, interaction: discord.Interaction, button: ui.Button):
        view = ui.View()
        view.add_item(DepotSelect("delete"))
        await interaction.response.send_message("Select the depot you want to delete:", view=view, ephemeral=True)


class DepotFlightView(ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(DepotSelect("flight"))