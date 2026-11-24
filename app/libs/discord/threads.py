# app/features/airfield/threads.py
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import TypeVar

import discord

from app.libs.content.text import clip
from app.libs.discord.limits import MAX_THREAD_NAME


logger = logging.getLogger(__name__)
T = TypeVar("T")
NO_PINGS = discord.AllowedMentions.none()


async def create_forum_thread(
        guild: discord.Guild,
        forum_id: str | None,
        title: str,
        content: str | None = None,
        *,
        embed: discord.Embed | None = None,
        view: discord.ui.View | None = None,
        auto_archive_minutes: int | None = None,
) -> discord.Thread | None:

    forum = guild.get_channel(int(forum_id)) if forum_id else None
    if not isinstance(forum, discord.ForumChannel):
        return None
    options: dict = {}
    if embed is not None:
        options["embed"] = embed
    if view is not None:
        options["view"] = view
    if auto_archive_minutes is not None:
        options["auto_archive_duration"] = auto_archive_minutes

    try:
        created = await forum.created_thread(
            name=clip(title, MAX_THREAD_NAME), content=content, allowed_mentions=NO_PINGS, **options
        )
    except discord.HTTPException:
        logger.error("Could not created a thread in forum %s.", forum_id, exc_info=True)
        return None
    return created.thread

async def create_recorded_thread(
        guild: discord.Guild,
        forum_id: str | None,
        title: str,
        record: Callable[[discord.Thread | None], T],
        content: str | None = None,
        **options,
) -> T:
    thread = await created_forum_thread(guild, forum_id, title, content, **options)
    try:
        return record(thread)
    except Exception:
        if thread is not None:
            await delete_thread(guild, thread.id)
        raise

async def _set_state(thread: discord.Thread, *, archived: bool, locked: bool, reason: str | None = None, name: str | None = None) -> discord.Thread:
    if thread.archived:
        thread = await thread.edit(archived=False, reason=reason)
    options = {"name": name} if name else {}
    return await thread.edit(archived=archived, locked=locked, reason=reason, **options)

@asynccontextmanager
async def _opened(thread: discord.Thread):
    was_archived, was_locked = thread.archived, thread.locked
    if was_archived or was_locked:
        thread = await _set_state(thread, archived=False, locked=False)
        try:
            yield thread
        finally:
            if was_archived or was_locked:
                await _set_state(thread, archived=was_archived, locked=was_locked)

async def edit_thread_start(guild: discord.Guild, thread_id: int | str, **edits) -> bool:
    thread = await fetch_thread(guild, thread_id)
    if not thread:
        return False

    try:
        async with _opened(thread) as opened:
            await opened.get_partial_message(opened.id).edit(**edits))
        return True
    except
        discord.HTTPException:
        logger.error("")


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