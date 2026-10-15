import discord
from discord import ui
from app.libs.views.forms import FormAction, FormError, FormField, FormView, simple_options
from app.libs.views.views import MAX_SELECT_OPTIONS, BaseView, FacilitySelect
from app.features.airfield.repository import STOCK_SOURCES, AirfieldRepository
from app.libs.discord.threads import update_thread_state, send_thread_message
from app.features.airfield.views.depot.flight import MISSION_PRESETS, checkout_and_log, finish_flight
from app.features.airfield.dashboard import refresh_controls
from app.features.airfield.views.depot.modals import (
    AddStockModal,
    CustomMissionModal,
    add_stock,
    log_stock_added,
    stock_added_text,
)

STOCK_FORM_SECONDS = 300  # longer than the usual 30s reply: people take a moment to fill in three dropdowns


class MissionSelect(ui.Select):
    def __init__(self, airfield_id: int, plane_type: str):
        self.airfield_id = airfield_id
        self.plane_type = plane_type

        options = [discord.SelectOption(label=m) for m in MISSION_PRESETS]
        super().__init__(placeholder="Select mission / operation type...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        mission = self.values[0]
        if mission == "Other":
            await interaction.response.send_modal(CustomMissionModal(self.airfield_id, self.plane_type))
        else:
            await checkout_and_log(interaction, self.airfield_id, self.plane_type, mission)


class MissionSelectView(BaseView):
    def __init__(self, airfield_id: int, plane_type: str):
        super().__init__(timeout=180)
        self.add_item(MissionSelect(airfield_id, plane_type))


def aircraft_options(airfield_id: int) -> list[discord.SelectOption]:
    """One option per configured aircraft, each showing how many are in this depot's stockpile."""
    stock = {s["plane_type"]: s["count"] for s in AirfieldRepository.get_stock_summary(airfield_id)}

    options = []
    for aircraft in AirfieldRepository.get_aircraft_types():
        # Stock stored under the older "Name (Role)" label still counts toward the plane.
        count = sum(
            n for stored, n in stock.items()
            if stored == aircraft.label or stored.startswith(f"{aircraft.label} (")
        )
        stock_text = f"{count} in stockpile" if count > 0 else "None registered in stockpile"
        options.append(discord.SelectOption(
            label=aircraft.label,
            value=aircraft.label,
            description=f"{aircraft.description} · {stock_text}"[:100],
        ))
    return options


class AircraftSelect(ui.Select):
    def __init__(self, airfield_id: int):
        self.airfield_id = airfield_id

        options = aircraft_options(airfield_id)
        if not options:
            options = [discord.SelectOption(label="No aircraft configured", value="NONE")]

        super().__init__(placeholder="Choose an aircraft type...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "NONE":
            await interaction.send("No aircraft types are configured.")
            return
        await self.on_pick(interaction, self.values[0])

    async def on_pick(self, interaction: discord.Interaction, plane_type: str):
        raise NotImplementedError


class CheckoutAircraftSelect(AircraftSelect):
    async def on_pick(self, interaction: discord.Interaction, plane_type: str):
        view = MissionSelectView(self.airfield_id, plane_type)
        await interaction.send(f"Select the mission for **{plane_type}**:", view=view)


class PlaneSelectView(BaseView):
    def __init__(self, airfield_id: int):
        super().__init__(timeout=180)
        self.add_item(CheckoutAircraftSelect(airfield_id))


def build_stock_form(airfield_id: int) -> FormView:
    """Adding stock in one message: aircraft, source and quantity dropdowns, then Add Stock to save."""

    async def submit(interaction: discord.Interaction, values: dict) -> str:
        if not add_stock(airfield_id, values["plane_type"], str(interaction.user.id), values["source"], values["quantity"]):
            raise FormError("That depot is no longer active in the current war.")
        return f"Added {stock_added_text(values['plane_type'], values['source'], values['quantity'])} to the stockpile."

    async def done(interaction: discord.Interaction, values: dict):
        await log_stock_added(interaction, airfield_id, values["plane_type"], values["source"], values["quantity"])

    async def custom_quantity(interaction: discord.Interaction, values: dict):
        await interaction.response.send_modal(AddStockModal(airfield_id, values["plane_type"], values["source"]))

    return FormView(
        [
            FormField("plane_type", "an aircraft", "Choose an aircraft type...", aircraft_options(airfield_id)),
            FormField("source", "where the stock is from (produced, purchased or other)",
                      "Where is it from?", simple_options(STOCK_SOURCES)),
            FormField("quantity", "a quantity", "How many?", simple_options(range(1, MAX_SELECT_OPTIONS + 1)),
                      default="1", convert=int),
        ],
        submit=submit,
        submit_label="Add Stock",
        submit_emoji="📦",
        done=done,
        actions=[FormAction("Custom Quantity...", custom_quantity)],
        timeout=STOCK_FORM_SECONDS,
    )


class DepotSelect(FacilitySelect):
    def __init__(self, action: str):
        self.action = action
        super().__init__(
            AirfieldRepository.get_airfields(),
            placeholder="Choose an airfield depot...",
            empty_label="No depots available",
            empty_message="There are no depots available.",
        )

    async def on_pick(self, interaction: discord.Interaction, airfield_id: int):
        if self.action == "add_stock":
            if not AirfieldRepository.get_aircraft_types():
                await interaction.send("No aircraft types are configured.")
                return
            await interaction.send(
                "Add aircraft stock - choose the aircraft, where it is from and how many, then press Add Stock:",
                view=build_stock_form(airfield_id),
                delete_after=STOCK_FORM_SECONDS
            )
        elif self.action == "view_details":
            depot = AirfieldRepository.get_depot_by_id(airfield_id)
            stock = AirfieldRepository.get_stock_summary(airfield_id)
            stock_str = "\n".join([f"• **{s['plane_type']}**: {s['count']}" for s in stock]) or "No planes registered in stock."
            await interaction.send(
                f"**{depot['name']}**\n"
                f"Location: **{depot['location']}**\n\n"
                f"**Stock Inventory:**\n{stock_str}"
            )
        elif self.action == "delete":
            depot = AirfieldRepository.get_depot_by_id(airfield_id)
            AirfieldRepository.delete_airfield(airfield_id)
            await interaction.send("Depot deleted. Its thread has been locked and archived.")
            if depot and depot["thread_id"]:
                await send_thread_message(
                    interaction.guild, depot["thread_id"],
                    f"🗑️ {interaction.user.mention} has deleted this depot. This thread is now locked."
                )
                await update_thread_state(interaction.guild, depot["thread_id"], False, "Depot deleted")
            await refresh_controls(interaction.guild)
        elif self.action == "flight":
            view = PlaneSelectView(airfield_id)
            await interaction.send("Select the aircraft type you are taking out:", view=view)


class DestinationSelect(ui.Select):
    """For a returned Transport flight: the depot the aircraft was delivered to."""
    def __init__(self, source_airfield_id: int):
        depots = AirfieldRepository.get_airfields()
        options = [
            discord.SelectOption(
                label=d["name"][:100], value=str(d["id"]),
                description=("Departed from here - " if d["id"] == source_airfield_id else "") + f"Location: {d['location']}"[:80]
            )
            for d in depots[:25]
        ]
        if not options:
            options = [discord.SelectOption(label="No depots available", value="NONE")]
        super().__init__(placeholder="Choose the destination depot...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "NONE":
            await interaction.send("There are no depots available.")
            return
        await finish_flight(interaction, "Returned", int(self.values[0]))


class DestinationSelectView(BaseView):
    def __init__(self, source_airfield_id: int):
        super().__init__(timeout=180)
        self.add_item(DestinationSelect(source_airfield_id))



