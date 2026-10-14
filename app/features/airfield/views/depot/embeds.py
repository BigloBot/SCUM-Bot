import discord
from app.core import settings
from app.features.airfield.repository import AirfieldRepository
from app.libs.discord.embeds import EmbedField, build_embed


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
    description = (
        f"Active war: **War {war}**\n\n"
        "Take aircraft out, log returns, and manage depots and stockpiles with the buttons below. "
        "Replies are only visible to you."
    )
    depots = AirfieldRepository.get_airfields()
    if not depots:
        return build_embed(
            title="Airfield Control Panel",
            description=description,
            color=discord.Color.blue(),
            fields=[EmbedField("Aircraft in stock", "No depots yet. Use **Create Depot** to add one.")],
        )

    summary = summarize_stock(AirfieldRepository.get_total_stock(), AirfieldRepository.get_aircraft_types())
    total = sum(count for _, count in summary)
    lines = "\n".join(f"{name}: **{count}**" for name, count in summary) or "No aircraft configured."
    return build_embed(
        title="Airfield Control Panel",
        description=description,
        color=discord.Color.blue(),
        fields=[EmbedField(
            f"Aircraft in stock: {total} across {len(depots)} depot{'s' if len(depots) != 1 else ''}", lines
        )],
    )


