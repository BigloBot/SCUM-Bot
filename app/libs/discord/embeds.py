"""Small, safe primitives for rendering Discord embeds from feature data."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import discord

MAX_EMBED_FIELDS = 25
MAX_FIELD_NAME_LENGTH = 256
MAX_FIELD_VALUE_LENGTH = 1024


@dataclass(frozen=True)
class EmbedField:
    """A Discord embed field before it is rendered."""

    name: str
    value: str
    inline: bool = False


def build_embed(
    *,
    title: str,
    color: discord.Colour,
    description: str | None = None,
    fields: Iterable[EmbedField] = (),
    footer: str | None = None,
    timestamp: bool = False,
) -> discord.Embed:
    """Build a bounded Discord embed from declarative content sections."""
    embed = discord.Embed(title=title[:MAX_FIELD_NAME_LENGTH], description=description, color=color)
    for field in list(fields)[:MAX_EMBED_FIELDS]:
        embed.add_field(
            name=field.name[:MAX_FIELD_NAME_LENGTH],
            value=field.value[:MAX_FIELD_VALUE_LENGTH] or "\u200b",
            inline=field.inline,
        )
    if footer:
        embed.set_footer(text=footer[:2048])
    if timestamp:
        embed.timestamp = discord.utils.utcnow()
    return embed