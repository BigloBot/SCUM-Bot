import discord
from discord import ui
from app.libs.views.views import BaseView, FacilitySelect
from app.features.airfield.repository import AirfieldRepository
from app.libs.discord.threads import update_thread_state, send_thread_message
from app.features.airfield.views.utils import MISSION_PRESETS, checkout_and_log, finish_flight
from app.features.airfield.dashboard import refresh_controls, refresh_kill_board
from app.features.airfield.views.modals import AddStockModal, CustomMissionModal

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


class AircraftSelect(ui.Select):
    def __init__(self, airfield_id: int):
        self.airfield_id = airfield_id

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


class StockAircraftSelect(AircraftSelect):
    async def on_pick(self, interaction: discord.Interaction, plane_type: str):
        await interaction.response.send_modal(AddStockModal(self.airfield_id, plane_type))


class PlaneSelectView(BaseView):
    def __init__(self, airfield_id: int):
        super().__init__(timeout=180)
        self.add_item(CheckoutAircraftSelect(airfield_id))


class StockSelectView(BaseView):
    def __init__(self, airfield_id: int):
        super().__init__(timeout=180)
        self.add_item(StockAircraftSelect(airfield_id))


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
            await interaction.send("Select the aircraft to add:", view=StockSelectView(airfield_id))
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



MAX_KILLS_PER_REPORT = 5  # a Discord dropdown holds at most 25 options


async def open_kill_type_selection(interaction: discord.Interaction, flight_id: int | None):
    kill_types = AirfieldRepository.get_kill_types()
    if not kill_types:
        await interaction.send("No kill types are configured.")
        return
    view = BaseView(timeout=180)
    view.add_item(KillTypeSelect(kill_types, flight_id))
    await interaction.send("Which aircraft did you shoot down?", view=view)


class KillReportFlightChoiceView(BaseView):
    """Lets a pilot without an active flight choose a completed flight or an unbound report."""

    def __init__(self, previous_flight):
        super().__init__(timeout=180)
        self.previous_flight_id = previous_flight["id"]

    @ui.button(label="Previous Flight", style=discord.ButtonStyle.primary)
    async def previous_flight(self, interaction: discord.Interaction, button: ui.Button):
        await open_kill_type_selection(interaction, self.previous_flight_id)

    @ui.button(label="Custom Kill", style=discord.ButtonStyle.secondary)
    async def custom_kill(self, interaction: discord.Interaction, button: ui.Button):
        await open_kill_type_selection(interaction, None)


class KillTypeSelect(ui.Select):
    """Step 1 of reporting kills: which aircraft was shot down."""

    def __init__(self, kill_types, flight_id: int | None):
        self.kill_types = {t.key: t for t in kill_types}
        self.flight_id = flight_id
        options = [
            discord.SelectOption(label=t.label[:100], value=t.key, description=t.description[:100])
            for t in list(kill_types)[:25]
        ]
        super().__init__(placeholder="Choose the aircraft you shot down...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        kill_type = self.kill_types[self.values[0]]
        view = BaseView(timeout=180)
        view.add_item(KillCountSelect(kill_type, self.flight_id))
        await interaction.send(f"How many **{kill_type.label}** were shot down?", view=view)


class KillCountSelect(ui.Select):
    """Step 2: how many kills to record against the selected flight or custom report."""

    def __init__(self, kill_type, flight_id: int | None):
        self.kill_type = kill_type
        self.flight_id = flight_id
        options = [discord.SelectOption(label=str(n), value=str(n)) for n in range(1, MAX_KILLS_PER_REPORT + 1)]
        super().__init__(placeholder="Choose how many...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        count = int(self.values[0])
        try:
            report_id = AirfieldRepository.add_kill_report(
                str(interaction.user.id), {self.kill_type.key: count}, self.flight_id
            )
        except ValueError:
            await interaction.send("That flight is no longer available. Start a new kill report to choose again.")
            return
        if report_id is None:
            await interaction.send("Nothing was recorded.")
            return
        await interaction.send(
            f"Recorded **{count}x {self.kill_type.label}**.",
            view=ReportAnotherView(), delete_after=60,
        )
        await refresh_kill_board(interaction.guild)


class ReportAnotherView(BaseView):
    def __init__(self):
        super().__init__(timeout=60)

    @ui.button(label="Report another aircraft", style=discord.ButtonStyle.secondary)
    async def another(self, interaction: discord.Interaction, button: ui.Button):
        await open_kill_report(interaction)


async def open_kill_report(interaction: discord.Interaction):
    """Bind a report to an active flight, or let the pilot choose their latest flight or a custom report."""
    user_id = str(interaction.user.id)
    active_flight = AirfieldRepository.get_user_active_flight_in_war(user_id)
    if active_flight:
        await open_kill_type_selection(interaction, active_flight["id"])
        return

    previous_flight = AirfieldRepository.get_user_latest_completed_flight(user_id)
    if previous_flight:
        await interaction.send(
            f"No active flight. Report kills against your previous **{previous_flight['plane_type']}** "
            f"flight ({previous_flight['status']}), or record a custom kill?",
            view=KillReportFlightChoiceView(previous_flight),
        )
        return

    await open_kill_type_selection(interaction, None)