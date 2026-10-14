"""Pilot statistics: top aces by kills (with K:D) and busiest pilots by sorties (with F/D)."""
import discord

TOP_N = 10
MEDALS = ["🥇", "🥈", "🥉"]


def ratio(count: int, deaths: int) -> float:
    """`count` per death. A pilot with no deaths yet is treated as having one, so their ratio is just `count`."""
    return count / max(deaths, 1)


def rank_pilots(stats: list[dict], limit: int = TOP_N) -> dict[str, list[dict]]:
    """
    Adds `kd` and `fd` to each pilot and returns two leaderboards:
      top_aces:      most kills first (ties: better K:D, then fewer deaths); pilots with no kills aren't listed.
      busiest_pilots: most finished flights first (ties: better F/D, then more kills); pilots with no flights
                      aren't listed.
    """
    pilots = [dict(p, kd=ratio(p["kills"], p["deaths"]), fd=ratio(p["flights"], p["deaths"])) for p in stats]
    top_aces = sorted(
        (p for p in pilots if p["kills"]),
        key=lambda p: (-p["kills"], -p["kd"], p["deaths"])
    )[:limit]
    busiest_pilots = sorted(
        (p for p in pilots if p["flights"]),
        key=lambda p: (-p["flights"], -p["fd"], -p["kills"])
    )[:limit]
    return {"top_aces": top_aces, "busiest_pilots": busiest_pilots}


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}{'' if n == 1 else 's'}"


def _ace_line(index: int, pilot: dict) -> str:
    rank = MEDALS[index] if index < len(MEDALS) else f"{index + 1}."
    return (
        f"{rank} <@{pilot['user_id']}> - **{_plural(pilot['kills'], 'kill')}** · "
        f"K:D **{pilot['kd']:.2f}** ({_plural(pilot['deaths'], 'death')})"
    )


def _sorties_line(index: int, pilot: dict) -> str:
    rank = MEDALS[index] if index < len(MEDALS) else f"{index + 1}."
    return (
        f"{rank} <@{pilot['user_id']}> - **{_plural(pilot['flights'], 'sortie')}** · "
        f"F/D **{pilot['fd']:.2f}** ({_plural(pilot['deaths'], 'death')})"
    )


def _field_value(pilots: list[dict], line) -> str:
    return "\n".join(line(i, p) for i, p in enumerate(pilots))[:1024]


def build_stats_embed(war: int, stats: list[dict]) -> discord.Embed:
    ranked = rank_pilots(stats)
    embed = discord.Embed(title=f"Pilot Stats - War {war}", color=discord.Color.gold())
    if not ranked["top_aces"] and not ranked["busiest_pilots"]:
        embed.description = "No kills or finished flights recorded yet this war."
        return embed

    embed.description = (
        "K:D is kills per death and F/D is finished flights (sorties) per death; losses count as sorties. "
        "A pilot with no deaths yet is counted as having one."
    )
    embed.add_field(
        name="Top Ace (K:D)",
        value=_field_value(ranked["top_aces"], _ace_line) if ranked["top_aces"] else "No kills reported yet.",
        inline=False
    )
    embed.add_field(
        name="Busiest Pilots (F/D)",
        value=_field_value(ranked["busiest_pilots"], _sorties_line) if ranked["busiest_pilots"] else "No sorties finished yet.",
        inline=False
    )
    return embed
