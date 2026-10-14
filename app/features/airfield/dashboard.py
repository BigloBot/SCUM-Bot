"""Airfield dashboard composition and ordering policy."""
import discord

from app.features.airfield.views.depot.embeds import build_panel_embed
from app.features.airfield.views.kills.embeds import build_kill_board_embed
from app.features.airfield.repository import AirfieldRepository
from app.libs.discord.panels import PersistentPanel

CONTROLS_CHANNEL_KEY = "controls_channel_id"
CONTROLS_MESSAGE_KEY = "controls_message_id"
BOARD_CHANNEL_KEY = "kills_channel_id"
BOARD_MESSAGE_KEY = "kills_message_id"


def build_controls_view():
    from app.features.airfield.views.depot.controls import DepotManagementView
    return DepotManagementView()


def build_kill_board_view():
    from app.features.airfield.views.kills.controls import KillBoardView
    return KillBoardView()

controls_panel = PersistentPanel(
    get_setting=AirfieldRepository.get_config,
    set_setting=AirfieldRepository.set_config,
    target_channel_key=CONTROLS_CHANNEL_KEY,
    message_channel_key=CONTROLS_CHANNEL_KEY,
    message_key=CONTROLS_MESSAGE_KEY,
    build_embed=build_panel_embed,
    build_view=build_controls_view,
    name="airfield controls",
)

kill_board_panel = PersistentPanel(
    get_setting=AirfieldRepository.get_config,
    set_setting=AirfieldRepository.set_config,
    target_channel_key=CONTROLS_CHANNEL_KEY,
    message_channel_key=BOARD_CHANNEL_KEY,
    message_key=BOARD_MESSAGE_KEY,
    build_embed=build_kill_board_embed,
    build_view=build_kill_board_view,
    name="airfield kill board",
)


async def refresh_controls(guild: discord.Guild) -> str:
    """Refresh only the depot controls after stock or flight state changes."""
    return await controls_panel.refresh(guild)


async def refresh_kill_board(guild: discord.Guild) -> str:
    """Refresh only the kill board after kill-report changes."""
    return await kill_board_panel.refresh(guild)


async def refresh_control_panel(guild: discord.Guild, channel: discord.TextChannel | None = None) -> str:
    """Refresh controls and ensure the kill board remains immediately below them."""
    result = await controls_panel.refresh(guild, channel)
    if result == "posted":
        # A newly posted controls message lands below the existing board.
        await kill_board_panel.clear(guild)
    if result in ("posted", "updated"):
        await kill_board_panel.refresh(guild)
    return result