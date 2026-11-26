"""Lifecycle management for persistent Discord embed panels."""
from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Literal

import discord

logger = logging.getLogger(__name__)

PanelResult = Literal["updated", "posted", "no_channel", "failed"]

GetSetting = Callable[[str], str | None]
SetSetting = Callable[[str, str], None]

_claimed_keys: set[str] = set()


def _claim(*keys: str) -> None:
    taken = _claimed_keys.intersection(keys)
    if taken:
        raise ValueError(f"panel settings key already in use: {', '.join(sorted(taken))}")
    _claimed_keys.update(keys)


class PersistentPanel:
    """One embed message (with an optional view) that is kept up to date in place. `key` namespaces its settings."""

    def __init__(
            self,
            key: str,
            *,
            build_embed: Callable[[], discord.Embed],
            build_view: Callable[[], discord.ui.View] | None = None,
            name: str,
    ) -> None:
        self.message_key = f"{key}_message_id"
        self.message_channel_key = f"{key}_message_channel_id"
        _claim(self.message_key, self.message_channel_key)
        self.build_embed = build_embed
        self.build_view = build_view
        self.name = name


class PanelStack:
    """
    Panels posted one under the other in a single channel, in the order given. When one has to be posted again
    (it was deleted, or the channel changed) every panel below it is posted again too, so the order never breaks.
    """

    def __init__(
            self,
            channel_key: str,
            panels: Sequence[PersistentPanel],
            *,
            get_setting: GetSetting,
            set_setting: SetSetting,
    ) -> None:
        if not panels:
            raise ValueError("a panel stack needs at least one panel")
        _claim(channel_key)
        self.channel_key = channel_key
        self.panels = tuple(panels)
        self.get_setting = get_setting
        self.set_setting = set_setting

    def channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        """The channel the stack lives in, if one is set and still exists."""
        channel_id = self.get_setting(self.channel_key)
        channel = guild.get_channel(int(channel_id)) if channel_id else None
        return channel if isinstance(channel, discord.TextChannel) else None

    async def sync(self, guild: discord.Guild) -> PanelResult:
        """Brings every panel up to date in place, posting any that are missing."""
        return await self._apply(guild, self.channel(guild), repost=False, only=None)

    async def refresh(self, guild: discord.Guild, panel: PersistentPanel) -> PanelResult:
        """Brings one panel up to date in place. If it has to be posted again, the panels below follow it."""
        return await self._apply(guild, self.channel(guild), repost=False, only={panel})

    async def rebuild(self, guild: discord.Guild, channel: discord.TextChannel | None = None) -> PanelResult:
        """Deletes and posts every panel again, in `channel` (which then becomes the stack's channel) if given."""
        if channel is not None:
            self.set_setting(self.channel_key, str(channel.id))
        return await self._apply(guild, channel or self.channel(guild), repost=True, only=None)

    async def _apply(
            self,
            guild: discord.Guild,
            target: discord.TextChannel | None,
            *,
            repost: bool,
            only: set[PersistentPanel] | None,
    ) -> PanelResult:
        if target is None:
            return "no_channel"

        results: list[PanelResult] = []
        for panel in self.panels:
            if not repost and only is not None and panel not in only:
                continue
            if repost:
                await self._clear(guild, panel)
            result = await self._refresh_panel(guild, panel, target)
            results.append(result)
            if result == "posted":
                repost = True

        if "failed" in results:
            return "failed"
        return "posted" if "posted" in results else "updated"

    async def _clear(self, guild: discord.Guild, panel: PersistentPanel) -> None:
        """Deletes the panel's message (if it still exists) and forgets it."""
        channel_id = self.get_setting(panel.message_channel_key) or self.get_setting(self.channel_key)
        message_id = self.get_setting(panel.message_key)
        self.set_setting(panel.message_key, "")
        if not channel_id or not message_id:
            return
        channel = guild.get_channel(int(channel_id))
        if channel is None:
            return
        try:
            await channel.get_partial_message(int(message_id)).delete()
        except discord.NotFound:
            return
        except discord.HTTPException:
            logger.warning("Could not delete %s message %s.", panel.name, message_id, exc_info=True)

    async def _refresh_panel(
            self, guild: discord.Guild, panel: PersistentPanel, target: discord.TextChannel
    ) -> PanelResult:
        message_id = self.get_setting(panel.message_key)
        posted_in = self.get_setting(panel.message_channel_key)
        if message_id and posted_in and posted_in != str(target.id):
            await self._clear(guild, panel)  # the stack moved channels: the old message has to go
            message_id = None

        embed = panel.build_embed()
        view = panel.build_view() if panel.build_view is not None else None
        try:
            if message_id:
                try:
                    await target.get_partial_message(int(message_id)).edit(embed=embed, view=view)
                    return "updated"
                except discord.NotFound:
                    pass  # deleted by hand: post it again below
            message = await (target.send(embed=embed, view=view) if view is not None else target.send(embed=embed))
        except discord.HTTPException:
            logger.error("Failed to refresh %s in channel %s.", panel.name, target.id, exc_info=True)
            return "failed"

        self.set_setting(panel.message_channel_key, str(target.id))
        self.set_setting(panel.message_key, str(message.id))
        return "posted"
