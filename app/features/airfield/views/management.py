import discord
from discord import ui
from app.core.permissions import is_admin
from app.core.ui import BaseView
from app.features.airfield.permissions import can_use_airfield
from app.features.airfield.repository import AirfieldRepository
from app.features.airfield.views.modals import CreateDepotModal, StructuredKillModal
from app.features.airfield.views.selects import DepotSelect

def describe_report(report) -> str:
    outcome = "returned" if report["status"] == "Returned" else "lost"
    return f"**{report['plane_type']}**, {outcome}, **{report['kills']}** kills"


async def send_fix_report(interaction: discord.Interaction, pilot: discord.abc.User = None):
    """
    Corrects a reported sortie. A pilot fixes their own most recent report. Admins can also pick any pilot
    (or pass one in) and then choose which of that pilot's reports to fix.
    """
    admin = is_admin(interaction.user)
    if pilot is not None and pilot.id != interaction.user.id and not admin:
        await interaction.send("Only admins can fix another pilot's report.")
        return

    if admin and pilot is None:
        view = BaseView()
        view.add_item(AdminPilotSelect())
        await interaction.send("Select the pilot whose report you want to fix:", view=view)
        return

    target = pilot or interaction.user
    if target.id != interaction.user.id:
        await send_report_choice(interaction, target)
        return

    report = AirfieldRepository.get_last_report(str(target.id))
    if not report:
        await interaction.send("You don't have a reported flight to fix in this war.")
        return
    await interaction.send(
        f"Your last report: {describe_report(report)}.\n"
        "Select the correct outcome to open the kill sheet with your reported numbers filled in:",
        view=FlightReturnStatusView(report, report=report)
    )


async def send_report_choice(interaction: discord.Interaction, pilot: discord.abc.User):
    reports = AirfieldRepository.get_recent_reports(str(pilot.id))
    if not reports:
        await interaction.send(f"{pilot.mention} has no reported flights in this war.", allowed_mentions=discord.AllowedMentions.none())
        return
    view = BaseView()
    view.add_item(ReportSelect(reports))
    await interaction.send(
        f"Select the report to fix for {pilot.mention} (newest first):",
        view=view, allowed_mentions=discord.AllowedMentions.none()
    )


class AdminPilotSelect(ui.UserSelect):
    def __init__(self):
        super().__init__(placeholder="Choose a pilot...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            await interaction.send("Only admins can fix another pilot's report.")
            return
        await send_report_choice(interaction, self.values[0])


class ReportSelect(ui.Select):
    def __init__(self, reports):
        options = [
            discord.SelectOption(
                label=f"{r['plane_type']} - {'Returned' if r['status'] == 'Returned' else 'Lost'} - {r['kills']} kills"[:100],
                value=str(r["id"]),
                description=f"Report #{r['id']}"
            )
            for r in reports[:25]
        ]
        super().__init__(placeholder="Choose a report...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        report = AirfieldRepository.get_report(int(self.values[0]))
        if not report or not is_admin(interaction.user):
            await interaction.send("That report can't be corrected.")
            return
        await interaction.send(
            f"Fixing: {describe_report(report)}.\n"
            "Select the correct outcome to open the kill sheet with the reported numbers filled in:",
            view=FlightReturnStatusView(report, report=report)
        )


class FlightReturnStatusView(BaseView):
    def __init__(self, flight, report=None):
        super().__init__(timeout=180)
        self.report = report
        plane = "Aircraft"
        if flight:
            try:
                plane = flight["plane_type"]
            except Exception:
                plane = str(flight)
        self.plane_type = plane

    @ui.button(label="Returned", style=discord.ButtonStyle.green, emoji="🛬")
    async def returned(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(StructuredKillModal(self.plane_type, "Returned", self.report))

    @ui.button(label="Loss", style=discord.ButtonStyle.danger, emoji="💥")
    async def loss(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(StructuredKillModal(self.plane_type, "Loss", self.report))


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
            f"Logging your **{active_flight['plane_type']}** flight. Select the outcome to open the kill sheet:",
            view=FlightReturnStatusView(active_flight)
        )

    @ui.button(label="Fix Last Report", style=discord.ButtonStyle.secondary, custom_id="scum:fix_report", row=0)
    async def fix_report(self, interaction: discord.Interaction, button: ui.Button):
        await send_fix_report(interaction)

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