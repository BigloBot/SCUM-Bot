"""Airfield statistics: top aces by kills (with K:D), busiest pilots by sorties (with F/D), and production."""
import discord
from app.features.airfield.views.depot.embeds import summarize_stock
from app.libs.discord.embeds import rank_marker

TOP_N = 10


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
    rank = rank_marker(index)
    return (
        f"{rank} <@{pilot['user_id']}> - **{_plural(pilot['kills'], 'kill')}** · "
        f"K:D **{pilot['kd']:.2f}** ({_plural(pilot['deaths'], 'death')})"
    )


def _sorties_line(index: int, pilot: dict) -> str:
    rank = rank_marker(index)
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


def build_production_embed(war: int, production: dict, planes, active_war: int) -> discord.Embed:
    """
    Aircraft commissioned into the air fleet in a war, with losses: a summary, a per-aircraft breakdown
    (configured order, legacy labels folded in) and the top producers. Past wars are worded in the past tense.
    """
    source = production.get("source")
    title = f"Production Stats - War {war}" + (f" ({source})" if source else "")
    embed = discord.Embed(title=title, color=discord.Color.green())
    total, lost = production["total"], production["lost"]
    # Losses aren't tracked per source, so a source-filtered report is about commissioned aircraft only.
    if source:
        lost = 0
    if not total and not lost:
        qualifier = f" {source.lower()}" if source else ""
        embed.description = (
            f"No{qualifier} aircraft have been added to the SCUM air fleet yet this war." if war == active_war
            else f"No{qualifier} aircraft were added to the SCUM air fleet during War {war}."
        )
        return embed

    kind = f"{source.lower()} aircraft" if source else "aircraft"
    if war == active_war:
        have_been = "has been" if total == 1 else "have been"
        commissioned = f"**{total}** {kind} {have_been} commissioned into the SCUM air fleet this war"
        losses = "none have been lost" if not lost else f"**{lost}** {'has' if lost == 1 else 'have'} been lost"
    else:
        was = "was" if total == 1 else "were"
        commissioned = f"**{total}** {kind} {was} commissioned into the SCUM air fleet during War {war}"
        losses = "none were lost" if not lost else f"**{lost}** {'was' if lost == 1 else 'were'} lost"
    summary = f"{commissioned}." if source else f"{commissioned}, and {losses}."
    embed.description = (
        f"{summary}\n"
        "*Aircraft returning from a flight or moved by a transport aren't counted as new.*"
    )

    produced = dict(summarize_stock(production["by_type"], planes))
    if source:
        lines = [f"{name}: **{count}** commissioned" for name, count in produced.items()]
        embed.description += "\n*Losses aren't tracked by source, so they aren't shown here.*"
    else:
        lost_by_type = dict(summarize_stock(production["lost_by_type"], planes))
        names = list(produced) + [n for n in lost_by_type if n not in produced]
        lines = [f"{name}: **{produced.get(name, 0)}** commissioned · **{lost_by_type.get(name, 0)}** lost" for name in names]
    embed.add_field(name="By aircraft", value="\n".join(lines)[:1024], inline=False)

    if not source:
        embed.add_field(
            name="By source",
            value="\n".join(f"{name}: **{count}**" for name, count in production["by_source"]),
            inline=False
        )

    if production["producers"]:
        lines = []
        for i, producer in enumerate(production["producers"]):
            rank = rank_marker(i)
            lines.append(f"{rank} <@{producer['user_id']}> - **{producer['count']}** aircraft")
        embed.add_field(name="Top Producers", value="\n".join(lines)[:1024], inline=False)
    return embed
