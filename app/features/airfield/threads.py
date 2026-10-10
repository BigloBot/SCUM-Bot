import logging
import discord
from app.features.airfield.repository import AirfieldRepository

logger = logging.getLogger(__name__)

MAX_THREAD_NAME = 100  # Discord's limit for thread names

# Log lines mention people for readability, but must never ping them.
NO_PINGS = discord.AllowedMentions.none()


def depot_thread_title(war_number: int, name: str, location: str) -> str:
    """Forum thread title: 'War-<no.> - <name> - <location>' (trimmed to Discord's limit)."""
    title = f"War-{war_number} - {name} - {location}"
    if len(title) > MAX_THREAD_NAME:
        title = title[:MAX_THREAD_NAME - 1].rstrip() + "…"
    return title


async def fetch_thread(guild: discord.Guild, thread_id) -> discord.Thread | None:
    """Gets a thread from cache, falling back to the API (archived threads are usually not cached)."""
    thread_id = int(thread_id)
    thread = guild.get_thread(thread_id)
    if thread is not None:
        return thread
    try:
        channel = await guild.fetch_channel(thread_id)
    except discord.NotFound:
        return None
    return channel if isinstance(channel, discord.Thread) else None


async def post_to_depot_thread(guild: discord.Guild, depot, message: str) -> bool:
    """Posts a log line to a depot's thread. `depot` is an airfields row. Mentions never ping."""
    if not depot or not depot["thread_id"]:
        return False
    try:
        thread = await fetch_thread(guild, depot["thread_id"])
        if thread is None:
            logger.warning(f"Thread {depot['thread_id']} for depot {depot['code']} no longer exists.")
            return False
        was_archived = thread.archived
        if was_archived:
            # Archived threads reject new messages until reopened (e.g. a late return log from a past war).
            await thread.edit(archived=False, locked=thread.locked)
        await thread.send(message, allowed_mentions=NO_PINGS)
        if was_archived:
            await thread.edit(archived=True, locked=thread.locked)
        return True
    except Exception as e:
        logger.error(f"Failed to send log to thread {depot['thread_id']}: {e}")
        return False


async def set_thread_open(guild: discord.Guild, thread_id, is_open: bool, reason: str) -> str:
    """
    Opens (unarchived + unlocked) or closes (archived + locked) a thread.
    Returns 'changed', 'unchanged', 'missing' or 'failed'.
    """
    try:
        thread = await fetch_thread(guild, thread_id)
        if thread is None:
            return "missing"
        if is_open and not thread.archived and not thread.locked:
            return "unchanged"
        if not is_open and thread.archived and thread.locked:
            return "unchanged"
        # Archived/locked are sent together so a locked+archived thread can be reopened in one edit.
        await thread.edit(archived=not is_open, locked=not is_open, reason=reason)
        return "changed"
    except Exception as e:
        logger.error(f"Failed to {'open' if is_open else 'close'} thread {thread_id}: {e}")
        return "failed"


async def close_depot_thread(guild: discord.Guild, depot, reason: str) -> str:
    if not depot or not depot["thread_id"]:
        return "unchanged"
    return await set_thread_open(guild, depot["thread_id"], False, reason)


async def sync_war_threads(guild: discord.Guild, active_war: int) -> dict:
    """
    Makes every depot thread match the active war:
      - ACTIVE depots of the active war -> unarchived and unlocked
      - everything else (other wars, deleted depots) -> archived and locked
    Safe to run repeatedly, so switching back to an earlier war reopens exactly that war's threads.
    """
    counts = {"changed": 0, "unchanged": 0, "missing": 0, "failed": 0}
    for depot in AirfieldRepository.get_all_war_airfields():
        if not depot["thread_id"]:
            continue
        should_be_open = depot["war_number"] == active_war and depot["status"] == "ACTIVE"
        reason = (
            f"War {active_war} is now active" if should_be_open
            else f"War {depot['war_number']} is not the active war (War {active_war})"
            if depot["status"] == "ACTIVE" else "Depot deleted"
        )
        result = await set_thread_open(guild, depot["thread_id"], should_be_open, reason)
        counts[result] += 1
    return counts
