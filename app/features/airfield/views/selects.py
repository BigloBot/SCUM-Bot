import discord
from discord import ui
from app.core.ui import BaseView
from app.features.airfield.repository import AirfieldRepository
from app.features.airfield.threads import update_thread_state, send_thread_message
from app.features.airfield.views.utils import MISSION_PRESETS, checkout_and_log
from app.features.airfield.views.modals import AddStockModal, CustomMissionModal

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


class AircraftSelect(ui.Select):
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
            await interaction.send("No aircraft types are configured.")
            return
        await self.on_pick(interaction, self.values[0])

    async def on_pick(self, interaction: discord.Interaction, plane_type: str):
        raise NotImplementedError


class CheckoutAircraftSelect(AircraftSelect):
    async def on_pick(self, interaction: discord.Interaction, plane_type: str):
        view = MissionSelectView(self.depot_code, plane_type)
        await interaction.send(f"Select the mission for **{plane_type}**:", view=view)


class StockAircraftSelect(AircraftSelect):
    async def on_pick(self, interaction: discord.Interaction, plane_type: str):
        await interaction.response.send_modal(AddStockModal(self.depot_code, plane_type))


class PlaneSelectView(BaseView):
    def __init__(self, depot_code: str):
        super().__init__(timeout=180)
        self.add_item(CheckoutAircraftSelect(depot_code))


class StockSelectView(BaseView):
    def __init__(self, depot_code: str):
        super().__init__(timeout=180)
        self.add_item(StockAircraftSelect(depot_code))


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
            await interaction.send("There are no depots available.")
            return

        code = self.values[0]
        if self.action == "add_stock":
            await interaction.send("Select the aircraft to add:", view=StockSelectView(code))
        elif self.action == "view_details":
            depot = AirfieldRepository.get_depot(code)
            stock = AirfieldRepository.get_stock_summary(code)
            stock_str = "\n".join([f"• **{s['plane_type']}**: {s['count']}" for s in stock]) or "No planes registered in stock."
            await interaction.send(
                f"**{depot['name']}**\n"
                f"Location: **{depot['location']}**\n\n"
                f"**Stock Inventory:**\n{stock_str}"
            )
        elif self.action == "delete":
            depot = AirfieldRepository.get_depot(code)
            AirfieldRepository.delete_airfield(code)
            await interaction.send("Depot deleted. Its thread has been locked and archived.")
            await send_thread_message(
                interaction.guild, depot,
                f"🗑️ {interaction.user.mention} has deleted this depot. This thread is now locked."
            )
            await update_thread_state(interaction.guild, depot, "Depot deleted", reason="depot deleted")
        elif self.action == "flight":
            view = PlaneSelectView(code)
            await interaction.send("Select the aircraft type you are taking out:", view=view)