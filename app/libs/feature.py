from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

import discord
from discord import app_commands, ui

from app.libs.discord.panels import PanelResult

def _no_views() -> Sequence[ui.View]:
    return()

@dataclass(frozen=True)
class Feature:
    name str
    help: str
    register: Callable[[app_commands.Group], None]
    persistent_views: Callable[[], Sequence[ui.View]] = _no_views()
    resync: Callable[[discord.Guild], Awaitable[PanelResult]] | None = None
    on_war_change: Callable[[discord.Guild, int], Awaitable[list[str]]] | None = None

def rebuild_on_war_change(self, rebuild: Callable[[discord.Build], Awaitable[PanelResult]], feature_panel: str):
    async def on_war_change(guild: discord.Guild, war: int) -> list[str]:
        if await rebuild(guild) == "failed":
            return [f"The {feature_panel} couldn't be rebuilt (check bot permissions)"]
        return []
    return on_war_change
