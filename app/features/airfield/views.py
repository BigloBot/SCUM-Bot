import logging
import discord
from discord import ui
from app.features.airfield.repository import AirfieldRepository
from app.features.airfield.threads import (
    close_depot_thread,
    depot_thread_title,
    post_to_depot_thread,
)

logger = logging.getLogger(__name__)

# Standard mission presets
MISSION_PRESETS = [
    "Large Ship Escort",
    "Heavy Bomber Escort",
    "Paratrooper Deployment",
    "Transport",
    "QRF",
    "Other"
]

INTERNAL_ERROR = "An internal error occurred. Please try again, and let an admin know if it keeps happening."


# ==================== SHARED HELPERS ====================

async def send_internal_error(interaction: discord.Interaction):
    """Generic error for the user; the details only go to the bot's logs."""
    try:
        if interaction.response.is_done():
            await interaction.followup.send(INTERNAL_ERROR, ephemeral=True)
        else:
            await interaction.response.send_message(INTERNAL_ERROR, ephemeral=True)
    except Exception:
        logger.error("Could not deliver the internal error message to the user.")


class BaseView(ui.View):
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: ui.Item) -> None:
        logger.error(f"Error in {type(self).__name__}: {error}", exc_info=(type(error), error, error.__traceback__))
        await send_internal_error(interaction)


class BaseModal(ui.Modal):
    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.error(f"Error in {type(self).__name__}: {error}", exc_info=(type(error), error, error.__traceback__))
        await send_internal_error(interaction)


# Helper function to auto-log stockpile events in forum threads
async def log_to_depot_thread(guild: discord.Guild, depot_code: str, message: str, airfield_id: int = None):
    # An explicit airfield_id targets that exact depot row (e.g. the one a flight left from);
    # otherwise the code resolves to the current war's depot.
    if airfield_id is not None:
        depot = AirfieldRepository.get_depot_by_id(airfield_id)
    else:
        depot = AirfieldRepository.get_depot(depot_code)
    await post_to_depot_thread(guild, depot, message)


def article(noun: str) -> str:
    """'a' or 'an' for the given (plain, unformatted) noun."""
    return "an" if noun[:1].lower() in "aeiou" else "a"


def join_natural(parts: list[str]) -> str:
    if len(parts) <= 2:
        return " and ".join(parts)
    return ", ".join(parts[:-1]) + f", and {parts[-1]}"


async def checkout_and_log(interaction: discord.Interaction, depot_code: str, plane_type: str, mission: str):
    """Checks a plane out for the pilot, confirms to them, and logs it in the depot thread."""
    user_id = str(interaction.user.id)
    success = AirfieldRepository.checkout_plane(depot_code, plane_type, mission, user_id)
    if not success:
        await interaction.response.send_message(
            "You already have an active flight, or this depot is no longer active. "
            "Log your return first with `/return`.",
            ephemeral=True
        )
        return

    depot = AirfieldRepository.get_depot(depot_code)
    location = depot["location"] if depot else "Unknown"
    await interaction.response.send_message(
        f"Checked out **{plane_type}** from **{depot['name'] if depot else depot_code}** ({location}).\n"
        f"Mission: **{mission}**\n"
        f"Good hunting.",
        ephemeral=True
    )
    await log_to_depot_thread(
        interaction.guild,
        depot_code,
        f"🛫 {interaction.user.mention} has taken out {article(plane_type)} **{plane_type}** for **{mission}**."
    )


# ==================== DEPOT MODALS ====================

class CreateDepotModal(BaseModal, title="Create Airfield Depot"):
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
                f"A depot with that {duplicate} is already active in this war.",
                ephemeral=True
            )
            return

        # Creating the forum thread can take longer than Discord's 3 second response window.
        await interaction.response.defer(ephemeral=True)

        war_number = AirfieldRepository.get_active_war()
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
                        name=depot_thread_title(war_number, name, location),
                        content=thread_content,
                        allowed_mentions=discord.AllowedMentions.none()
                    )
                    thread = created_thread.thread
                except Exception as e:
                    logger.error(f"Error creating forum thread: {e}")

        AirfieldRepository.add_airfield(name, code, location, str(thread.id) if thread else None)
        await interaction.followup.send(f"Depot **{name}** created. Location: **{location}**.", ephemeral=True)


class AddStockModal(BaseModal, title="Add Aircraft Stock"):
    quantity = ui.TextInput(label="Quantity", placeholder="1", default="1", required=True, max_length=3)

    def __init__(self, depot_code: str, plane_type: str):
        super().__init__(title=f"Add {plane_type}"[:45])  # Discord caps modal titles at 45 characters
        self.depot_code = depot_code
        self.plane_type = plane_type

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = int(self.quantity.value.strip())
            if qty <= 0:
                raise ValueError()
        except ValueError:
            await interaction.response.send_message("Please enter a valid positive number for the quantity.", ephemeral=True)
            return

        plane = self.plane_type
        user_id = str(interaction.user.id)

        for _ in range(qty):
            if not AirfieldRepository.add_plane(self.depot_code, plane, user_id):
                await interaction.response.send_message("That depot is no longer active in the current war.", ephemeral=True)
                return

        await interaction.response.send_message(f"Added **{qty}x {plane}** to the stockpile.", ephemeral=True)
        await log_to_depot_thread(
            interaction.guild,
            self.depot_code,
            f"📦 {interaction.user.mention} has added **{qty}x {plane}** to the stockpile."
        )


class CustomMissionModal(BaseModal, title="Check Out Aircraft - Custom Mission"):
    usecase = ui.TextInput(label="Flight Purpose / Operation Details", placeholder="Describe custom operation...", required=True, style=discord.TextStyle.paragraph)

    def __init__(self, depot_code: str, plane_type: str):
        super().__init__()
        self.depot_code = depot_code
        self.plane_type = plane_type

    async def on_submit(self, interaction: discord.Interaction):
        await checkout_and_log(interaction, self.depot_code, self.plane_type, self.usecase.value.strip())


# ==================== STEP 2: FLIGHT RETURN KILL SHEET MODAL ====================

class StructuredKillModal(BaseModal, title="Sortie Kill Sheet"):
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

        def count(field: ui.TextInput) -> int:
            try:
                return max(0, int(field.value.strip() or "0"))
            except ValueError:
                return 0

        t_count = count(self.toxot_kills)
        h_count = count(self.harpy_kills)
        p_count = count(self.peregrine_kills)

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
            await interaction.response.send_message("You do not have an active flight to log.", ephemeral=True)
            return

        outcome = "returned" if self.status == "Returned" else "lost"
        await interaction.response.send_message(
            f"Flight logged: **{self.plane_type}** {outcome}.\n"
            f"Air kills: **{air_summary}**\n"
            f"Notes: {extra_notes or 'None'}",
            ephemeral=True
        )

        # Log the outcome in the depot thread the flight left from
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
        await log_to_depot_thread(interaction.guild, completed["airfield_code"], log_msg, completed["airfield_id"])


# ==================== STEP 1: FLIGHT RETURN BUTTONS ====================

class FlightReturnStatusView(BaseView):
    """Step 1: Pilot clicks Returned or Loss to trigger the Kill Sheet popup."""
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
            await checkout_and_log(interaction, self.depot_code, self.plane_type, mission)


class MissionSelectView(BaseView):
    def __init__(self, depot_code: str, plane_type: str):
        super().__init__(timeout=180)
        self.add_item(MissionSelect(depot_code, plane_type))


# ==================== CHECKOUT AIRCRAFT SELECT ====================

class AircraftSelect(ui.Select):
    """
    The one aircraft dropdown, built from the shared aircraft_types list and annotated with this
    depot's stock. Used for both taking aircraft out and adding stock; subclasses decide what a pick does.
    """
    def __init__(self, depot_code: str):
        self.depot_code = depot_code

        stock = {s["plane_type"]: s["count"] for s in AirfieldRepository.get_stock_summary(depot_code)}

        options = []
        for aircraft in AirfieldRepository.get_aircraft_types():
            count = stock.get(aircraft["label"], 0)
            desc = f"{count} in stockpile" if count > 0 else "None registered in stockpile"
            options.append(discord.SelectOption(label=aircraft["label"], description=desc))
        if not options:
            options = [discord.SelectOption(label="No aircraft configured", value="NONE")]

        super().__init__(placeholder="Choose an aircraft type...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "NONE":
            await interaction.response.send_message("No aircraft types are configured.", ephemeral=True)
            return
        await self.on_pick(interaction, self.values[0])

    async def on_pick(self, interaction: discord.Interaction, plane_type: str):
        raise NotImplementedError


class CheckoutAircraftSelect(AircraftSelect):
    async def on_pick(self, interaction: discord.Interaction, plane_type: str):
        view = MissionSelectView(self.depot_code, plane_type)
        await interaction.response.send_message(f"Select the mission for **{plane_type}**:", view=view, ephemeral=True)


class StockAircraftSelect(AircraftSelect):
    async def on_pick(self, interaction: discord.Interaction, plane_type: str):
        await interaction.response.send_modal(AddStockModal(self.depot_code, plane_type))


class PlaneSelectView(BaseView):
    """Aircraft choice for taking a plane out of a depot."""
    def __init__(self, depot_code: str):
        super().__init__(timeout=180)
        self.add_item(CheckoutAircraftSelect(depot_code))


class StockSelectView(BaseView):
    """Aircraft choice for adding stock to a depot."""
    def __init__(self, depot_code: str):
        super().__init__(timeout=180)
        self.add_item(StockAircraftSelect(depot_code))


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
            await interaction.response.send_message("There are no depots available.", ephemeral=True)
            return

        code = self.values[0]
        if self.action == "add_stock":
            await interaction.response.send_message(
                "Select the aircraft to add:", view=StockSelectView(code), ephemeral=True
            )
        elif self.action == "view_details":
            depot = AirfieldRepository.get_depot(code)
            stock = AirfieldRepository.get_stock_summary(code)
            stock_str = "\n".join([f"• **{s['plane_type']}**: {s['count']}" for s in stock]) or "No planes registered in stock."
            await interaction.response.send_message(
                f"**{depot['name']}**\n"
                f"Location: **{depot['location']}**\n\n"
                f"**Stock Inventory:**\n{stock_str}",
                ephemeral=True
            )
        elif self.action == "delete":
            depot = AirfieldRepository.get_depot(code)
            AirfieldRepository.delete_airfield(code)
            await interaction.response.send_message("Depot deleted. Its thread has been locked and archived.", ephemeral=True)
            # Log the deletion, then close the thread (history stays in the database and the thread).
            await post_to_depot_thread(
                interaction.guild, depot,
                f"🗑️ {interaction.user.mention} has deleted this depot. This thread is now locked."
            )
            await close_depot_thread(interaction.guild, depot, "Depot deleted")
        elif self.action == "flight":
            view = PlaneSelectView(code)
            await interaction.response.send_message("Select the aircraft type you are taking out:", view=view, ephemeral=True)


class DepotManagementView(BaseView):
    def __init__(self, forum_channel: discord.ForumChannel):
        super().__init__(timeout=None)
        self.forum_channel = forum_channel

    @ui.button(label="Create Depot", style=discord.ButtonStyle.green, emoji="➕")
    async def create_depot(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(CreateDepotModal())

    @ui.button(label="Add Stock", style=discord.ButtonStyle.primary, emoji="📦")
    async def add_stock(self, interaction: discord.Interaction, button: ui.Button):
        view = BaseView()
        view.add_item(DepotSelect("add_stock"))
        await interaction.response.send_message("Select the depot to add stock to:", view=view, ephemeral=True)

    @ui.button(label="View Depots", style=discord.ButtonStyle.secondary, emoji="📋")
    async def view_depots(self, interaction: discord.Interaction, button: ui.Button):
        view = BaseView()
        view.add_item(DepotSelect("view_details"))
        await interaction.response.send_message("Select the depot to view:", view=view, ephemeral=True)

    @ui.button(label="Delete Depot", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_depot(self, interaction: discord.Interaction, button: ui.Button):
        view = BaseView()
        view.add_item(DepotSelect("delete"))
        await interaction.response.send_message("Select the depot to delete:", view=view, ephemeral=True)


class DepotFlightView(BaseView):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(DepotSelect("flight"))
