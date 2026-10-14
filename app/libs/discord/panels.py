"""Lifecycle management for persistent Discord embed panels."""
from __future__ import annotations

import logging
from collections.abc import Callable

import discord

logger = logging.getLogger(__name__)

PanelResult = str


class PersistentPanel:
    """Keeps one configured embed message present and current in a Discord text channel.

    The feature supplies only its storage functions, key names, and factories for the embed and optional
    view. This class handles message movement, deletion, edits, re-posting, and ID persistence.
    """

    def __init__(
        self,
        *,
        get_setting: Callable[[str], str | None],
        set_setting: Callable[[str, str], None],
        target_channel_key: str,
        message_channel_key: str,
        message_key: str,
        build_embed: Callable[[], discord.Embed],
        build_view: Callable[[], discord.ui.View] | None = None,
        name: str,
    ) -> None:
        self.get_setting = get_setting
        self.set_setting = set_setting
        self.target_channel_key = target_channel_key
        self.message_channel_key = message_channel_key
        self.message_key = message_key
        self.build_embed = build_embed
        self.build_view = build_view
        self.name = name

    def _stored_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        channel_id = self.get_setting(self.target_channel_key)
        channel = guild.get_channel(int(channel_id)) if channel_id else None
        return channel if isinstance(channel, discord.TextChannel) else None

    async def _delete(self, guild: discord.Guild, channel_id: str | None, message_id: str | None) -> None:
        if not channel_id or not message_id:
            return
        try:
            channel = guild.get_channel(int(channel_id))
            if channel is not None:
                await channel.get_partial_message(int(message_id)).delete()
        except Exception:
            pass  # already gone, or the bot can no longer access it

    async def clear(self, guild: discord.Guild) -> None:
        """Delete the tracked message if it remains, then clear its stored ID."""
        await self._delete(
            guild,
            self.get_setting(self.message_channel_key),
            self.get_setting(self.message_key),
        )
        self.set_setting(self.message_key, "")

    async def refresh(self, guild: discord.Guild, channel: discord.TextChannel | None = None) -> PanelResult:
        """Edit the tracked message or post it afresh. Returns updated, posted, no_channel, or failed."""
        target = channel or self._stored_channel(guild)
        if target is None:
            return "no_channel"

        old_channel_id = self.get_setting(self.message_channel_key)
        old_message_id = self.get_setting(self.message_key)
        moved = bool(old_channel_id) and int(old_channel_id) != target.id
        if moved:
            await self._delete(guild, old_channel_id, old_message_id)
            old_message_id = None

        embed = self.build_embed()
        view = self.build_view() if self.build_view else None
        try:
            if old_message_id and not moved:
                try:
                    await target.get_partial_message(int(old_message_id)).edit(embed=embed, view=view)
                    return "updated"
                except discord.NotFound:
                    pass
            message = await target.send(embed=embed, view=view)
        except Exception:
            logger.error("Failed to refresh %s in channel %s.", self.name, target.id, exc_info=True)
            return "failed"

        self.set_setting(self.message_channel_key, str(target.id))
        self.set_setting(self.message_key, str(message.id))
        return "posted"