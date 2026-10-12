import logging
import discord
from app.core import settings
from app.features.bank.repository import BankRepository

logger = logging.getLogger(__name__)

BANK_CHANNEL_KEY = "bank.channel_id"
BANK_CONTROLS_MESSAGE_KEY = "bank.controls_message_id"
BANK_BOARD_MESSAGE_KEY = "bank.board_message_id"


def build_controls_embed() -> discord.Embed:
    war = settings.get_active_war()
    embed = discord.Embed(
        title="Bank Control Panel",
        description=(
            f"Active war: **War {war}**\n\n"
            "Add officer stockpiles and keep their rare material counts up to date. "
            "All active stockpiles are summarized in the board below. "
            "Replies are only visible to you."
        ),
        color=discord.Color.blue()
    )
    totals, count = BankRepository.get_totals(war)
    lines = "\n".join(f"{label}: {amount:,}" for label, amount in totals.items()) or "No materials tracked."
    embed.add_field(
        name=f"Total across all stockpiles ({count} active)",
        value=f"```yaml\n{lines}\n```",
        inline=False
    )
    return embed


def build_board_embed() -> discord.Embed:
    war = settings.get_active_war()
    stockpiles = BankRepository.get_stockpiles()
    active_stockpiles = [
        s for s in stockpiles
        if s["status"] == "ACTIVE" and s["war_number"] == war
    ]

    embed = discord.Embed(
        title=f"📦 Active Officer Stockpiles (War {war})",
        color=discord.Color.gold()
    )

    if not active_stockpiles:
        embed.description = "No active stockpiles for this war yet. Use the **Add Stockpile** button above to create one."
        return embed

    for stockpile in active_stockpiles:
        balances, _ = BankRepository.get_summary(stockpile["id"])

        balance_lines = [f"  • {label}: {amount:,}" for label, amount in balances.items()]
        materials_text = "\n".join(balance_lines) if balance_lines else "  • No items recorded"

        field_value = (
            f"🔑 **Code:** `{stockpile['code']}` | 📍 **Location:** {stockpile['location']}\n"
            f"```yaml\n"
            f"Materials:\n"
            f"{materials_text}\n"
            f"```"
        )
        embed.add_field(name=f"📦 {stockpile['name']}", value=field_value, inline=False)

    embed.set_footer(text="Updated")
    embed.timestamp = discord.utils.utcnow()
    return embed

def get_board_channel(guild: discord.Guild) -> discord.TextChannel | None:
    channel_id = settings.get_setting(BANK_CHANNEL_KEY)
    channel = guild.get_channel(int(channel_id)) if channel_id else None
    return channel if isinstance(channel, discord.TextChannel) else None


async def _delete_message(channel: discord.TextChannel, message_id: str | None):
    if not message_id:
        return
    try:
        await channel.get_partial_message(int(message_id)).delete()
    except Exception:
        pass  # already gone or bot lost permission


async def sync_stockpile_board(guild: discord.Guild) -> str:
    """
    Updates the single stockpile board message in place, or creates it if missing.
    Returns 'updated', 'posted', 'no_channel' or 'failed'.
    """
    channel = get_board_channel(guild)
    if channel is None:
        return "no_channel"

    # The controls message shows the war-wide totals, so it changes whenever the board does.
    controls_msg_id = settings.get_setting(BANK_CONTROLS_MESSAGE_KEY)
    if controls_msg_id:
        try:
            await channel.get_partial_message(int(controls_msg_id)).edit(embed=build_controls_embed())
        except Exception as e:
            logger.warning(f"Could not refresh the bank controls message: {e}")

    board_msg_id = settings.get_setting(BANK_BOARD_MESSAGE_KEY)
    embed = build_board_embed()

    if board_msg_id:
        try:
            await channel.get_partial_message(int(board_msg_id)).edit(embed=embed)
            return "updated"
        except discord.NotFound:
            pass  # message was manually deleted, fall through to re-post

    try:
        message = await channel.send(embed=embed)
        settings.set_setting(BANK_BOARD_MESSAGE_KEY, str(message.id))
        return "posted"
    except Exception as e:
        logger.error(f"Failed to post the stockpile board in channel {channel.id}: {e}")
        return "failed"


async def resync_board(guild: discord.Guild) -> str:
    """
    Forces the bank controls message and stockpile board back in line: both are edited in place (re-attaching
    the control buttons), and if either was deleted the whole board is reposted.
    Returns 'updated', 'posted', 'no_channel' or 'failed'.
    """
    from app.features.bank.views import BankControlView  # imported here to keep modules decoupled

    channel = get_board_channel(guild)
    if channel is None:
        return "no_channel"

    controls_id = settings.get_setting(BANK_CONTROLS_MESSAGE_KEY)
    board_id = settings.get_setting(BANK_BOARD_MESSAGE_KEY)
    if not controls_id or not board_id:
        return await rebuild_board(guild)

    try:
        await channel.get_partial_message(int(controls_id)).edit(embed=build_controls_embed(), view=BankControlView())
        await channel.get_partial_message(int(board_id)).edit(embed=build_board_embed())
        return "updated"
    except discord.NotFound:
        return await rebuild_board(guild)  # one of them was deleted; repost both in the right order
    except Exception as e:
        logger.error(f"Failed to resync the bank board in channel {channel.id}: {e}")
        return "failed"


async def rebuild_board(guild: discord.Guild, channel: discord.TextChannel = None) -> str:
    """
    Rebuilds the bank channel: posts the control panel first, followed by a single board 
    message summarizing all active stockpiles.
    """
    from app.features.bank.views import BankControlView  # imported here to keep modules decoupled

    old_channel = get_board_channel(guild)
    target = channel or old_channel
    if target is None:
        return "no_channel"

    old_controls_id = settings.get_setting(BANK_CONTROLS_MESSAGE_KEY)
    old_board_id = settings.get_setting(BANK_BOARD_MESSAGE_KEY)

    # Post the control panel
    try:
        controls = await target.send(embed=build_controls_embed(), view=BankControlView())
    except Exception as e:
        logger.error(f"Failed to post the bank control panel in channel {target.id}: {e}")
        return "failed"

    # Post the board message below the control panel
    try:
        board_msg = await target.send(embed=build_board_embed())
    except Exception as e:
        logger.error(f"Failed to post the bank stockpile board in channel {target.id}: {e}")
        await _delete_message(target, str(controls.id))
        return "failed"

    # Clean up old messages from previous setups
    if old_channel is not None:
        if old_controls_id:
            await _delete_message(old_channel, old_controls_id)
        if old_board_id:
            await _delete_message(old_channel, old_board_id)

    # Store settings for the new panel messages
    settings.set_setting(BANK_CHANNEL_KEY, str(target.id))
    settings.set_setting(BANK_CONTROLS_MESSAGE_KEY, str(controls.id))
    settings.set_setting(BANK_BOARD_MESSAGE_KEY, str(board_msg.id))

    return "posted"