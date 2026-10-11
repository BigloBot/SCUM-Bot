import asyncio
import logging
import discord
from app.features.airfield.repository import AirfieldRepository
from app.features.airfield.threads import send_thread_message

logger = logging.getLogger(__name__)

# ==================== INTERACTION EXTENSION ====================

async def _delete_later(message, delay: float):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except discord.HTTPException:
        pass


async def _interaction_send(
        self,
        content: str = None,
        *,
        ephemeral: bool = True,
        delete_after: float = 30.0,
        **kwargs
):
    """Sends an interaction response, defaulting to ephemeral=True and auto-deleting after 30s."""
    try:
        if not self.response.is_done():
            await self.response.send_message(content, ephemeral=ephemeral, **kwargs)
            message = await self.original_response() if delete_after else None
        else:
            # Webhook.send() has no delete_after, so fetch the sent message and delete it ourselves.
            message = await self.followup.send(content, ephemeral=ephemeral, wait=bool(delete_after), **kwargs)
    except discord.HTTPException:
        logger.error("Could not send an interaction response.", exc_info=True)
        return

    if delete_after and message is not None:
        asyncio.create_task(_delete_later(message, delete_after))

# Attach .send() directly to discord.Interaction so it's available everywhere automatically
discord.Interaction.send = _interaction_send

# ==================== CONSTANTS & HELPERS ====================

MISSION_PRESETS = [
    "Large Ship Escort",
    "Heavy Bomber Escort",
    "Paratrooper Deployment",
    "Transport",
    "QRF",
    "Other"
]

async def log_to_depot_thread(guild: discord.Guild, airfield_id: int, message: str):
    """Logs to the thread of exactly this depot (depots are addressed by id; passcodes are not unique)."""
    depot = AirfieldRepository.get_depot_by_id(airfield_id)
    if depot and depot["thread_id"]:
        await send_thread_message(guild, depot["thread_id"], message)


def article(noun: str) -> str:
    """'a' or 'an' for the given (plain, unformatted) noun."""
    return "an" if noun[:1].lower() in "aeiou" else "a"


def join_natural(parts: list[str]) -> str:
    if len(parts) <= 2:
        return " and ".join(parts)
    return ", ".join(parts[:-1]) + f", and {parts[-1]}"


async def checkout_and_log(interaction: discord.Interaction, airfield_id: int, plane_type: str, mission: str):
    user_id = str(interaction.user.id)
    success = AirfieldRepository.checkout_plane(airfield_id, plane_type, mission, user_id)
    if not success:
        await interaction.send(
            "You already have an active flight, or this depot is no longer active. "
            "Log your return first with `/scum airfield return`."
        )
        return

    depot = AirfieldRepository.get_depot_by_id(airfield_id)
    location = depot["location"] if depot else "Unknown"
    await interaction.send(
        f"Checked out **{plane_type}** from **{depot['name'] if depot else 'the depot'}** ({location}).\n"
        f"Mission: **{mission}**\n"
        f"Good hunting."
    )
    await log_to_depot_thread(
        interaction.guild,
        airfield_id,
        f"🛫 {interaction.user.mention} has taken out {article(plane_type)} **{plane_type}** for **{mission}**."
    )