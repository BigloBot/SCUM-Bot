# app/features/airfield/threads.py
import logging
import discord

logger = logging.getLogger(__name__)
NO_PINGS = discord.AllowedMentions.none()


async def fetch_thread(guild: discord.Guild, thread_id: int | str) -> discord.Thread | None:
    """Gets a thread from cache or API."""
    try:
        thread_id = int(thread_id)
    except (ValueError, TypeError):
        return None

    thread = guild.get_thread(thread_id)
    if thread is not None:
        return thread

    try:
        channel = await guild.fetch_channel(thread_id)
        return channel if isinstance(channel, discord.Thread) else None
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return None


async def send_thread_message(guild: discord.Guild, thread_id: int | str, content: str) -> bool:
    """Sends a message to a thread, temporarily unlocking it if locked."""
    thread = await fetch_thread(guild, thread_id)
    if not thread:
        return False

    try:
        was_locked = thread.locked
        if was_locked:
            await thread.edit(locked=False)

        await thread.send(content, allowed_mentions=NO_PINGS)

        if was_locked:
            await thread.edit(locked=True)
        return True
    except Exception as e:
        logger.error(f"Failed to post to thread {thread_id}: {e}")
        return False


async def update_thread_state(guild: discord.Guild, thread_id: int | str, is_open: bool, reason: str) -> str:
    """Sets a thread's archived/locked state."""
    thread = await fetch_thread(guild, thread_id)
    if not thread:
        return "missing"

    target_state = not is_open
    if thread.archived == target_state and thread.locked == target_state:
        return "unchanged"

    try:
        await thread.edit(archived=target_state, locked=target_state, reason=reason)
        return "changed"
    except Exception as e:
        logger.error(f"Failed to set thread state for {thread_id}: {e}")
        return "failed"