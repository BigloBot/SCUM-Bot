# app/features/airfield/service.py
import asyncio
import discord
from app.features.airfield.repository import AirfieldRepository
from app.features.airfield.threads import send_thread_message, update_thread_state

MAX_THREAD_NAME = 100


def format_depot_thread_title(war_number: int, name: str, location: str) -> str:
    """Domain rule for thread naming conventions."""
    title = f"War-{war_number} - {name} - {location}"
    if len(title) > MAX_THREAD_NAME:
        title = title[: MAX_THREAD_NAME - 1].rstrip() + "…"
    return title


async def log_depot_event(guild: discord.Guild, airfield_id: int, message: str) -> bool:
    """Business workflow to find depot data and dispatch thread log."""
    depot = AirfieldRepository.get_depot_by_id(airfield_id)

    if not depot or not depot["thread_id"]:
        return False

    return await send_thread_message(guild, depot["thread_id"], message)


async def sync_war_threads(guild: discord.Guild, active_war: int) -> dict[str, int]:
    """Business rule: determine which depots should be open vs closed for a war."""
    depots = [dict(d) for d in AirfieldRepository.get_all_war_airfields() if d["thread_id"]]
    if not depots:
        return {"changed": 0, "unchanged": 0, "missing": 0, "failed": 0}

    async def _sync_single(depot: dict):
        should_be_open = (depot["war_number"] == active_war) and (depot["status"] == "ACTIVE")

        if should_be_open:
            reason = f"War {active_war} is now active"
        elif depot["status"] == "ACTIVE":
            reason = f"War {depot['war_number']} is not active (Active: {active_war})"
        else:
            reason = "Depot deleted"

        return await update_thread_state(guild, depot["thread_id"], should_be_open, reason)

    results = await asyncio.gather(*[_sync_single(d) for d in depots], return_exceptions=True)

    counts = {"changed": 0, "unchanged": 0, "missing": 0, "failed": 0}
    for res in results:
        if isinstance(res, str) and res in counts:
            counts[res] += 1
        else:
            counts["failed"] += 1

    return counts