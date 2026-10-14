"""Pilot statistics: kill/death and flight/death ratios, best K/D and most planes lost."""
import discord

TOP_N = 10
MEDALS = ["🥇", "🥈", "🥉"]


def ratio(count: int, deaths: int) -> float:
    """`count` per death. A pilot with no deaths yet is treated as having one, so their ratio is just `count`."""
    return count / max(deaths, 1)


def rank_pilots(stats: list[dict], limit: int = TOP_N) -> dict[str, list[dict]]:
    """
    Adds `kd` and `fd` to each pilot and returns two leaderboards:
      best_kd:     most positive kill/death first (ties: more kills, then fewer deaths); pilots with no kills and
                   no deaths aren't ranked.
      most_losses: most planes lost first (ties: worse flights per death); pilots who lost none aren't listed.
    """
    pilots = [dict(p, kd=ratio(p["kills"], p["deaths"]), fd=ratio(p["flights"], p["deaths"])) for p in stats]
    best_kd = sorted(
        (p for p in pilots if p["kills"] or p["deaths"]),
        key=lambda p: (-p["kd"], -p["kills"], p["deaths"])
    )[:limit]
    most_losses = sorted(
        (p for p in pilots if p["deaths"]),
        key=lambda p: (-p["deaths"], p["fd"], -p["kills"])
    )[:limit]
    return {"best_kd": best_kd, "most_losses": most_losses}


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}{'' if n == 1 else 's'}"


def _line(index: int, pilot: dict) -> str:
    rank = MEDALS[index] if index < len(MEDALS) else f"{index + 1}."
    kd = f"K/D **{pilot['kd']:.2f}** ({_plural(pilot['kills'], 'kill')}, {_plural(pilot['deaths'], 'death')})"
    fd = f"F/D **{pilot['fd']:.2f}** ({_plural(pilot['flights'], 'flight')})" if pilot["flights"] else "no flights logged"
    return f"{rank} <@{pilot['user_id']}> - {kd} · {fd}"


def _field_value(pilots: list[dict]) -> str:
    return "\n".join(_line(i, p) for i, p in enumerate(pilots))[:1024]


def build_stats_embed(war: int, stats: list[dict]) -> discord.Embed:
    ranked = rank_pilots(stats)
    embed = discord.Embed(title=f"Pilot Stats - War {war}", color=discord.Color.gold())
    if not ranked["best_kd"] and not ranked["most_losses"]:
        embed.description = "No kills or finished flights recorded yet this war."
        return embed

    embed.description = (
        "K/D is kills per death and F/D is finished flights per death (losses count as flights). "
        "A pilot with no deaths yet is counted as having one."
    )
    if ranked["best_kd"]:
        embed.add_field(name="Best kill/death", value=_field_value(ranked["best_kd"]), inline=False)
    embed.add_field(
        name="Most planes lost",
        value=_field_value(ranked["most_losses"]) if ranked["most_losses"] else "Nobody has lost a plane yet.",
        inline=False
    )
    return embed
