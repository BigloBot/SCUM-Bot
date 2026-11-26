"""Airfield dashboard composition and ordering policy: the controls first, the kill board right below them."""
import discord

from app.core import settings
from app.features.airfield.views.depot.embeds import build_panel_embed
from app.features.airfield.views.kills.embeds import build_kill_board_embed
from app.libs.discord.panels import PanelResult, PanelStack, PersistentPanel

# These keys name settings that already exist in deployed databases, so panels posted before the
# move to PanelStack keep being edited in place instead of being posted a second time.
CONTROLS_CHANNEL_KEY = "controls_channel_id"
CONTROLS_PANEL_KEY = "controls"
KILL_BOARD_PANEL_KEY = "kills"


def build_controls_view():
    from app.features.airfield.views.depot.controls import DepotManagementView
    return DepotManagementView()


def build_kill_board_view():
    from app.features.airfield.views.kills.controls import KillBoardView
    return KillBoardView()


controls_panel = PersistentPanel(
    CONTROLS_PANEL_KEY,
    build_embed=build_panel_embed,
    build_view=build_controls_view,
    name="airfield controls",
)

kill_board_panel = PersistentPanel(
    KILL_BOARD_PANEL_KEY,
    build_embed=build_kill_board_embed,
    build_view=build_kill_board_view,
    name="airfield kill board",
)

# Order matters: whenever the controls are posted again, the kill board is posted again below them.
airfield_stack = PanelStack(
    CONTROLS_CHANNEL_KEY,
    [controls_panel, kill_board_panel],
    get_setting=settings.get_setting,
    set_setting=settings.set_setting,
)


async def refresh_controls(guild: discord.Guild) -> PanelResult:
    """Refresh only the depot controls after stock or flight state changes."""
    return await airfield_stack.refresh(guild, controls_panel)


async def refresh_kill_board(guild: discord.Guild) -> PanelResult:
    """Refresh only the kill board after kill-report changes."""
    return await airfield_stack.refresh(guild, kill_board_panel)


async def resync_dashboard(guild: discord.Guild) -> PanelResult:
    """Bring both panels up to date in place."""
    return await airfield_stack.sync(guild)


async def rebuild_dashboard(guild: discord.Guild, channel: discord.TextChannel | None = None) -> PanelResult:
    """Post both panels again, controls first, in `channel` (or the channel already set)."""
    return await airfield_stack.rebuild(guild, channel)
