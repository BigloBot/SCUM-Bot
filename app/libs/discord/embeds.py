"""Small, safe primitives for rendering Discord embeds from feature data."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import discord

MAX_EMBED_FIELDS = 25
MAX_FIELD_NAME_LENGTH = 256
MAX_FIELD_VALUE_LENGTH = 1024


# Medals, then keycap numbers: all emoji, so a ranked list lines up (a plain "4." is narrower than a medal).
_RANK_MARKERS = ["\U0001F947", "\U0001F948", "\U0001F949"] + [f"{n}\ufe0f\u20e3" for n in range(4, 10)] + ["\U0001F51F"]


def rank_marker(index: int) -> str:
    """Marker for a 0-based position in a ranked list: medals for the top 3, keycap numbers up to 10, then "11."."""
    return _RANK_MARKERS[index] if index < len(_RANK_MARKERS) else f"{index + 1}."


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