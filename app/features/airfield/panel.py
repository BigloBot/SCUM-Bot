import logging
import discord
from app.core import settings
from app.features.airfield.repository import AirfieldRepository

logger = logging.getLogger(__name__)


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


async def _delete_old_message(guild: discord.Guild, channel_id: str, message_id: str):
    try:
        channel = guild.get_channel(int(channel_id))
        if channel is not None:
            await channel.get_partial_message(int(message_id)).delete()
    except Exception:
        pass  # already gone, or the bot can no longer reach it


async def _refresh_controls(guild: discord.Guild, channel: discord.TextChannel = None) -> str:
    """
    Keeps the one permanent controls message up to date.
      - `channel` given: that becomes the controls channel (the old message is removed if it was elsewhere).
      - `channel` omitted: the stored channel is used (e.g. to refresh the active war shown).
    The existing message is edited in place; if it was deleted, a new one is posted.
    Returns 'posted', 'updated', 'no_channel' or 'failed'.
    """
    from app.features.airfield.views.management import DepotManagementView  # imported here to keep modules decoupled

    old_channel_id = AirfieldRepository.get_config("controls_channel_id")
    old_message_id = AirfieldRepository.get_config("controls_message_id")

    target = channel
    if target is None and old_channel_id:
        stored = guild.get_channel(int(old_channel_id))
        target = stored if isinstance(stored, discord.TextChannel) else None
    if target is None:
        return "no_channel"

    moved = bool(old_channel_id) and int(old_channel_id) != target.id
    if moved and old_message_id:
        await _delete_old_message(guild, old_channel_id, old_message_id)
        old_message_id = None

    embed = build_panel_embed()
    view = DepotManagementView()
    try:
        if old_message_id and not moved:
            try:
                await target.get_partial_message(int(old_message_id)).edit(embed=embed, view=view)
                return "updated"
            except discord.NotFound:
                pass  # the message was deleted; post a fresh one below
        message = await target.send(embed=embed, view=view)
    except Exception as e:
        logger.error(f"Failed to post the controls message in channel {target.id}: {e}")
        return "failed"

    AirfieldRepository.set_config("controls_channel_id", str(target.id))
    AirfieldRepository.set_config("controls_message_id", str(message.id))
    return "posted"


async def refresh_controls(guild: discord.Guild) -> str:
    """Re-renders just the controls message (e.g. after stock changed). Never raises; see _refresh_controls."""
    try:
        return await _refresh_controls(guild)
    except Exception:
        logger.error("Could not refresh the controls message.", exc_info=True)
        return "failed"


async def refresh_control_panel(guild: discord.Guild, channel: discord.TextChannel = None) -> str:
    """Refreshes the controls message, then the kill board so it always sits directly under it."""
    result = await _refresh_controls(guild, channel)
    if result == "posted":
        # A new controls message lands at the bottom of the channel, so the old board is now above it.
        await _delete_board_message(guild)
    if result in ("posted", "updated"):
        await refresh_kill_board(guild)
    return result


# ==================== KILL BOARD ====================

BOARD_MESSAGE_KEY = "kills_message_id"
BOARD_CHANNEL_KEY = "kills_channel_id"
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


async def _delete_board_message(guild: discord.Guild):
    channel_id = AirfieldRepository.get_config(BOARD_CHANNEL_KEY)
    message_id = AirfieldRepository.get_config(BOARD_MESSAGE_KEY)
    if channel_id and message_id:
        await _delete_old_message(guild, channel_id, message_id)
    AirfieldRepository.set_config(BOARD_MESSAGE_KEY, "")


async def refresh_kill_board(guild: discord.Guild) -> str:
    """
    Keeps the kill board message up to date in the controls channel (edited in place, reposted if deleted).
    Returns 'posted', 'updated', 'no_channel' or 'failed'.
    """
    controls_channel_id = AirfieldRepository.get_config("controls_channel_id")
    channel = guild.get_channel(int(controls_channel_id)) if controls_channel_id else None
    if not isinstance(channel, discord.TextChannel):
        return "no_channel"

    old_channel_id = AirfieldRepository.get_config(BOARD_CHANNEL_KEY)
    old_message_id = AirfieldRepository.get_config(BOARD_MESSAGE_KEY)
    if old_message_id and old_channel_id and int(old_channel_id) != channel.id:
        await _delete_old_message(guild, old_channel_id, old_message_id)
        old_message_id = None

    embed = build_kill_board_embed()
    try:
        if old_message_id:
            try:
                await channel.get_partial_message(int(old_message_id)).edit(embed=embed)
                return "updated"
            except discord.NotFound:
                pass  # deleted by hand; post a fresh one below
        message = await channel.send(embed=embed)
    except Exception as e:
        logger.error(f"Failed to post the kill board in channel {channel.id}: {e}")
        return "failed"

    AirfieldRepository.set_config(BOARD_CHANNEL_KEY, str(channel.id))
    AirfieldRepository.set_config(BOARD_MESSAGE_KEY, str(message.id))
    return "posted"
