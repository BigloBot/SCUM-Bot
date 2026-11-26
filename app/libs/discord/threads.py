"""Forum thread helpers: create, find, post to, edit and open/close threads, tolerating locked and archived ones."""
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Literal, TypeVar

import discord

from app.libs.content.text import clip
from app.libs.discord.limits import MAX_THREAD_NAME

logger = logging.getLogger(__name__)
T = TypeVar("T")
NO_PINGS = discord.AllowedMentions.none()

ThreadStateResult = Literal["changed", "unchanged", "missing", "failed"]


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
    """Starts a thread in the forum. None when no forum is set up, or when Discord refuses (the cause is logged)."""
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
        created = await forum.create_thread(
            name=clip(title, MAX_THREAD_NAME), content=content, allowed_mentions=NO_PINGS, **options
        )
    except discord.HTTPException:
        logger.error("Could not create a thread in forum %s.", forum_id, exc_info=True)
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
    """
    Creates a thread, then calls `record(thread)` to save it (`thread` is None when none could be made).
    If saving fails the thread is deleted again, so no thread is left behind with nothing pointing at it.
    """
    thread = await create_forum_thread(guild, forum_id, title, content, **options)
    try:
        return record(thread)
    except Exception:
        if thread is not None:
            await delete_thread(guild, thread.id)
        raise


async def fetch_thread(guild: discord.Guild, thread_id: int | str) -> discord.Thread | None:
    """Gets a thread from cache or the API. None when it is gone or the id isn't valid."""
    try:
        thread_id = int(thread_id)
    except (ValueError, TypeError):
        return None

    thread = guild.get_thread(thread_id)
    if thread is not None:
        return thread

    try:
        channel = await guild.fetch_channel(thread_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return None
    return channel if isinstance(channel, discord.Thread) else None


async def delete_thread(guild: discord.Guild, thread_id: int | str) -> bool:
    """Deletes a thread. False when it is already gone or can't be deleted."""
    thread = await fetch_thread(guild, thread_id)
    if thread is None:
        return False
    try:
        await thread.delete()
    except discord.HTTPException:
        logger.error("Could not delete thread %s.", thread_id, exc_info=True)
        return False
    return True


async def _set_state(
        thread: discord.Thread, *, archived: bool, locked: bool, reason: str | None = None
) -> discord.Thread:
    """Sets archived/locked. An archived thread has to be reopened before it can be edited at all."""
    if thread.archived:
        thread = await thread.edit(archived=False, reason=reason)
    return await thread.edit(archived=archived, locked=locked, reason=reason)


@asynccontextmanager
async def _opened(thread: discord.Thread):
    """Yields the thread unarchived and unlocked, then puts it back the way it was found."""
    was_archived, was_locked = thread.archived, thread.locked
    if was_archived or was_locked:
        thread = await _set_state(thread, archived=False, locked=False)
    try:
        yield thread
    finally:
        if was_archived or was_locked:
            try:
                await _set_state(thread, archived=was_archived, locked=was_locked)
            except discord.HTTPException:
                logger.error("Could not restore the state of thread %s.", thread.id, exc_info=True)


async def edit_thread_start(guild: discord.Guild, thread_id: int | str, **edits) -> bool:
    """Edits the first message of a forum thread (content, embed, view...). False if that couldn't be done."""
    thread = await fetch_thread(guild, thread_id)
    if thread is None:
        return False

    try:
        async with _opened(thread) as opened:
            await opened.get_partial_message(opened.id).edit(**edits)
    except discord.HTTPException:
        logger.error("Could not edit the first message of thread %s.", thread_id, exc_info=True)
        return False
    return True


async def send_thread_message(guild: discord.Guild, thread_id: int | str, content: str) -> bool:
    """Sends a message to a thread, temporarily unlocking and unarchiving it if needed."""
    thread = await fetch_thread(guild, thread_id)
    if thread is None:
        return False

    try:
        async with _opened(thread) as opened:
            await opened.send(content, allowed_mentions=NO_PINGS)
    except discord.HTTPException:
        logger.error("Failed to post to thread %s.", thread_id, exc_info=True)
        return False
    return True


async def update_thread_state(
        guild: discord.Guild, thread_id: int | str, is_open: bool, reason: str
) -> ThreadStateResult:
    """Opens a thread (unarchived, unlocked) or closes it (archived, locked)."""
    thread = await fetch_thread(guild, thread_id)
    if thread is None:
        return "missing"

    closed = not is_open
    if thread.archived == closed and thread.locked == closed:
        return "unchanged"

    try:
        await _set_state(thread, archived=closed, locked=closed, reason=reason)
    except discord.HTTPException:
        logger.error("Failed to set the state of thread %s.", thread_id, exc_info=True)
        return "failed"
    return "changed"
