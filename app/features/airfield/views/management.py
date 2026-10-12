import discord
from discord import ui
from app.core.ui import BaseView
from app.features.airfield.permissions import can_use_airfield
from app.features.airfield.repository import AirfieldRepository
from app.features.airfield.views.modals import CreateDepotModal
from app.features.airfield.views.selects import DepotSelect, DestinationSelectView, open_kill_report
from app.features.airfield.views.utils import finish_flight

class FlightReturnStatusView(BaseView):
    """Logs how the flight ended. A returned Transport flight also asks which depot it delivered to."""
    def __init__(self, flight):
        super().__init__(timeout=180)
        self.airfield_id = flight["airfield_id"]
        self.is_transport = (flight["usecase"] or "").strip().lower() == "transport"

    @ui.button(label="Returned", style=discord.ButtonStyle.green, emoji="🛬")
    async def returned(self, interaction: discord.Interaction, button: ui.Button):
        if self.is_transport:
            await interaction.send(
                "Transport flight: select the depot the aircraft was delivered to.",
                view=DestinationSelectView(self.airfield_id)
            )
        else:
            await finish_flight(interaction, "Returned")

    @ui.button(label="Loss", style=discord.ButtonStyle.danger, emoji="💥")
    async def loss(self, interaction: discord.Interaction, button: ui.Button):
        await finish_flight(interaction, "Loss")


class DepotFlightView(BaseView):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(DepotSelect("flight"))


class DepotManagementView(BaseView):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if can_use_airfield(interaction.user):
            return True
        await interaction.send("You don't have permission to use these controls.")
        return False

    @ui.button(label="Take Out Aircraft", style=discord.ButtonStyle.green, custom_id="scum:flight", row=0)
    async def take_out(self, interaction: discord.Interaction, button: ui.Button):
        if not AirfieldRepository.get_airfields():
            await interaction.send("There are no depots in the active war yet.")
            return
        await interaction.send("Select the depot you are taking an aircraft from:", view=DepotFlightView())

    @ui.button(label="Log Return", style=discord.ButtonStyle.primary, custom_id="scum:return", row=0)
    async def log_return(self, interaction: discord.Interaction, button: ui.Button):
        active_flight = AirfieldRepository.get_user_active_flight(str(interaction.user.id))
        if not active_flight:
            await interaction.send("You don't have an active flight to log.")
            return
        await interaction.send(
            f"Logging your **{active_flight['plane_type']}** flight. Select how it ended:",
            view=FlightReturnStatusView(active_flight)
        )

    @ui.button(label="Report Kills", style=discord.ButtonStyle.secondary, custom_id="scum:report_kills", row=0)
    async def report_kills(self, interaction: discord.Interaction, button: ui.Button):
        await open_kill_report(interaction)

    @ui.button(label="Create Depot", style=discord.ButtonStyle.secondary, custom_id="scum:create_depot", row=1)
    async def create_depot(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(CreateDepotModal())

    @ui.button(label="Add Stock", style=discord.ButtonStyle.secondary, custom_id="scum:add_stock", row=1)
    async def add_stock(self, interaction: discord.Interaction, button: ui.Button):
        view = BaseView()
        view.add_item(DepotSelect("add_stock"))
        await interaction.send("Select the depot to add stock to:", view=view)

    @ui.button(label="View Depots", style=discord.ButtonStyle.secondary, custom_id="scum:view_depots", row=1)
    async def view_depots(self, interaction: discord.Interaction, button: ui.Button):
        view = BaseView()
        view.add_item(DepotSelect("view_details"))
        await interaction.send("Select the depot to view:", view=view)

    @ui.button(label="Delete Depot", style=discord.ButtonStyle.danger, custom_id="scum:delete_depot", row=1)
    async def delete_depot(self, interaction: discord.Interaction, button: ui.Button):
        view = BaseView()
        view.add_item(DepotSelect("delete"))
        await interaction.send("Select the depot to delete:", view=view)