"""
The bank channel: one control panel message, followed by one panel per stockpile showing its
passcode, location and how many of each rare material it holds.
"""
import logging
import discord
from app.core import settings
from app.features.bank.repository import BankRepository

logger = logging.getLogger(__name__)

BANK_CHANNEL_KEY = "bank.channel_id"
BANK_CONTROLS_MESSAGE_KEY = "bank.controls_message_id"


def build_controls_embed() -> discord.Embed:
    war = settings.get_active_war()
    return discord.Embed(
        title="Bank Control Panel",
        description=(
            f"Active war: **War {war}**\n\n"
            "Add officer stockpiles and keep their rare material counts up to date. "
            "Every stockpile is listed below with its passcode and what it holds. "
            "Replies are only visible to you."
        ),
        color=discord.Color.blue()
    )


def build_stockpile_embed(stockpile) -> discord.Embed:
    balances, last_updated = BankRepository.get_summary(stockpile["id"])
    embed = discord.Embed(
        title=stockpile["name"],
        description=f"**Code:** `{stockpile['code']}`\n**Location:** {stockpile['location']}",
        color=discord.Color.gold()
    )
    for label, amount in balances.items():
        embed.add_field(name=label, value=f"{amount:,}", inline=True)
    embed.set_footer(text=f"War {stockpile['war_number']}  |  Last updated")
    embed.timestamp = last_updated
    return embed


def get_board_channel(guild: discord.Guild) -> discord.TextChannel | None:
    channel_id = settings.get_setting(BANK_CHANNEL_KEY)
    channel = guild.get_channel(int(channel_id)) if channel_id else None
    return channel if isinstance(channel, discord.TextChannel) else None


async def _delete_message(channel: discord.TextChannel, message_id: str):
    try:
        await channel.get_partial_message(int(message_id)).delete()
    except Exception:
        pass  # already gone, or the bot can no longer reach it


async def sync_stockpile_message(guild: discord.Guild, stockpile_id: int) -> str:
    """
    Brings one stockpile's panel in line with the database: edited in place, posted if it has none yet,
    or removed if the stockpile was deleted or belongs to another war.
    Returns 'updated', 'posted', 'removed', 'no_channel' or 'failed'.
    """
    stockpile = BankRepository.get_stockpile(stockpile_id)
    channel = get_board_channel(guild)
    if stockpile is None or channel is None:
        return "no_channel"

    is_shown = stockpile["status"] == "ACTIVE" and stockpile["war_number"] == settings.get_active_war()
    if not is_shown:
        if stockpile["message_id"]:
            await _delete_message(channel, stockpile["message_id"])
            BankRepository.set_message_id(stockpile_id, None)
        return "removed"

    embed = build_stockpile_embed(stockpile)
    try:
        if stockpile["message_id"]:
            try:
                await channel.get_partial_message(int(stockpile["message_id"])).edit(embed=embed)
                return "updated"
            except discord.NotFound:
                pass  # the panel was deleted; post a fresh one below
        message = await channel.send(embed=embed)
    except Exception as e:
        logger.error(f"Failed to post the panel for stockpile {stockpile_id}: {e}")
        return "failed"

    BankRepository.set_message_id(stockpile_id, str(message.id))
    return "posted"


async def rebuild_board(guild: discord.Guild, channel: discord.TextChannel = None) -> str:
    """
    Rebuilds the whole channel: control panel first, then a panel for each active stockpile of the
    active war, in creation order. Anything the bot posted before is removed.
      - `channel` given: that becomes the bank channel (the old board is removed from the previous one).
      - `channel` omitted: the stored channel is rebuilt, e.g. after a war switch.
    Returns 'posted', 'no_channel' or 'failed'.
    """
    from app.features.bank.views import BankControlView  # imported here to keep modules decoupled

    old_channel = get_board_channel(guild)
    target = channel or old_channel
    if target is None:
        return "no_channel"

    old_controls_id = settings.get_setting(BANK_CONTROLS_MESSAGE_KEY)
    old_panels = BankRepository.get_stockpiles_with_messages()

    # Post the new control panel first: if the bot can't post in this channel, nothing has been removed yet.
    try:
        controls = await target.send(embed=build_controls_embed(), view=BankControlView())
    except Exception as e:
        logger.error(f"Failed to post the bank control panel in channel {target.id}: {e}")
        return "failed"

    settings.set_setting(BANK_CHANNEL_KEY, str(target.id))
    settings.set_setting(BANK_CONTROLS_MESSAGE_KEY, str(controls.id))

    if old_channel is not None:
        if old_controls_id:
            await _delete_message(old_channel, old_controls_id)
        for panel in old_panels:
            await _delete_message(old_channel, panel["message_id"])
    BankRepository.clear_all_message_ids()

    try:
        for stockpile in BankRepository.get_stockpiles():
            message = await target.send(embed=build_stockpile_embed(stockpile))
            BankRepository.set_message_id(stockpile["id"], str(message.id))
    except Exception as e:
        logger.error(f"Failed to post the bank stockpile panels in channel {target.id}: {e}")
        return "failed"

    return "posted"
