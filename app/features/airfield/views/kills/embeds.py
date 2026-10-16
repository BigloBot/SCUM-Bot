"""Kill-board presentation."""
import discord

from app.core import settings
from app.features.airfield.repository import AirfieldRepository
from app.libs.discord.embeds import EmbedField, build_embed, rank_marker

# ==================== KILL BOARD ====================


def build_kill_board_embed() -> discord.Embed:
    war = settings.get_active_war()
    board = AirfieldRepository.get_kill_board(war)

    description = (
        f"**{board['total']}** kills reported this war."
        if board["total"] else "No kills reported yet this war."
    )
    fields = []

    if board["total"]:
        fields.append(EmbedField("Kills by aircraft", "\n".join(f"{label}: **{kills}**" for label, kills in board["types"])))
        lines = []
        for i, pilot in enumerate(board["pilots"]):
            rank = rank_marker(i)
            by_type = ", ".join(f"{n}x {label}" for label, n in pilot["by_type"])
            lines.append(f"{rank} <@{pilot['user_id']}> - **{pilot['kills']}** ({by_type})")
        fields.append(EmbedField("Top pilots (kills by aircraft)", "\n".join(lines)))

    return build_embed(
        title=f"Kill Board - War {war}",
        description=description,
        color=discord.Color.red(),
        fields=fields,
        timestamp=True,
    )

