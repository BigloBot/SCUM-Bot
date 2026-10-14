import discord
from app.core import settings
from app.features.airfield.repository import AirfieldRepository


def summarize_stock(rows, planes) -> list[tuple[str, int]]:
    """
    Stock per aircraft as (name, count): every configured plane in config order (zero included), then any stored
    type that isn't configured any more. Stock stored under the older "Name (Role)" label counts toward its plane.
    """
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["plane_type"]] = counts.get(row["plane_type"], 0) + row["count"]

    summary = []
    for plane in planes:
        legacy = [k for k in counts if k.startswith(f"{plane.label} (")]
        total = counts.pop(plane.label, 0) + sum(counts.pop(k) for k in legacy)
        summary.append((plane.label, total))
    summary.extend(sorted(counts.items()))
    return summary


def build_panel_embed() -> discord.Embed:
    war = settings.get_active_war()
    embed = discord.Embed(
        title="Airfield Control Panel",
        description=(
            f"Active war: **War {war}**\n\n"
            "Take aircraft out, log returns, and manage depots and stockpiles with the buttons below. "
            "Replies are only visible to you."
        ),
        color=discord.Color.blue()
    )

    depots = AirfieldRepository.get_airfields()
    if not depots:
        embed.add_field(name="Aircraft in stock", value="No depots yet. Use **Create Depot** to add one.", inline=False)
        return embed

    summary = summarize_stock(AirfieldRepository.get_total_stock(), AirfieldRepository.get_aircraft_types())
    total = sum(count for _, count in summary)
    lines = "\n".join(f"{name}: **{count}**" for name, count in summary) or "No aircraft configured."
    embed.add_field(
        name=f"Aircraft in stock: {total} across {len(depots)} depot{'s' if len(depots) != 1 else ''}",
        value=lines[:1024],
        inline=False
    )
    return embed


# ==================== KILL BOARD ====================

MEDALS = ["🥇", "🥈", "🥉"]


def build_kill_board_embed() -> discord.Embed:
    war = settings.get_active_war()
    board = AirfieldRepository.get_kill_board(war)

    embed = discord.Embed(title=f"Kill Board - War {war}", color=discord.Color.red())
    embed.description = (
        f"**{board['total']}** kills reported this war."
        if board["total"] else "No kills reported yet this war."
    )

    if board["total"]:
        embed.add_field(
            name="Kills by aircraft",
            value="\n".join(f"{label}: **{kills}**" for label, kills in board["types"])[:1024],
            inline=False
        )
        lines = []
        for i, pilot in enumerate(board["pilots"]):
            rank = MEDALS[i] if i < len(MEDALS) else f"{i + 1}."
            by_type = ", ".join(f"{n}x {label}" for label, n in pilot["by_type"])
            lines.append(f"{rank} <@{pilot['user_id']}> - **{pilot['kills']}** ({by_type})")
        embed.add_field(name="Top pilots (kills by aircraft)", value="\n".join(lines)[:1024], inline=False)

    embed.timestamp = discord.utils.utcnow()
    return embed

