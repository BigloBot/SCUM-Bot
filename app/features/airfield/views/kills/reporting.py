"""Kill-report interaction flow."""
import discord
from discord import ui

from app.features.airfield.dashboard import refresh_kill_board
from app.features.airfield.repository import AirfieldRepository
from app.libs.views.views import BaseView
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