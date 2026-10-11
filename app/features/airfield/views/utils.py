import asyncio
import logging
import discord
from app.features.airfield.repository import AirfieldRepository
from app.features.airfield.threads import send_thread_message

logger = logging.getLogger(__name__)

# ==================== INTERACTION EXTENSION ====================

async def _interaction_send(
        self,
        content: str = None,
        *,
        ephemeral: bool = True,
        delete_after: float = 30.0,
        **kwargs
):
    """Sends an interaction response, defaulting to ephemeral=True and auto-deleting after 30s."""
    if not self.response.is_done():
        await self.response.send_message(content, ephemeral=ephemeral, **kwargs)
        if delete_after:
            try:
                msg = await self.original_response()
                async def _delete_later():
                    await asyncio.sleep(delete_after)
                    try:
                        await msg.delete()
                    except discord.HTTPException:
                        pass
                asyncio.create_task(_delete_later())
            except discord.HTTPException:
                pass
    else:
        await self.followup.send(content, ephemeral=ephemeral, delete_after=delete_after, **kwargs)

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

async def log_to_depot_thread(guild: discord.Guild, depot_code: str, message: str, airfield_id: int = None):
    if airfield_id is not None:
        depot = AirfieldRepository.get_depot_by_id(airfield_id)
    else:
        depot = AirfieldRepository.get_depot(depot_code)
    await send_thread_message(guild, depot, message)


def article(noun: str) -> str:
    """'a' or 'an' for the given (plain, unformatted) noun."""
    return "an" if noun[:1].lower() in "aeiou" else "a"


def join_natural(parts: list[str]) -> str:
    if len(parts) <= 2:
        return " and ".join(parts)
    return ", ".join(parts[:-1]) + f", and {parts[-1]}"


async def checkout_and_log(interaction: discord.Interaction, depot_code: str, plane_type: str, mission: str):
    user_id = str(interaction.user.id)
    success = AirfieldRepository.checkout_plane(depot_code, plane_type, mission, user_id)
    if not success:
        await interaction.send(
            "You already have an active flight, or this depot is no longer active. "
            "Log your return first with `/scum airfield return`."
        )
        return

    depot = AirfieldRepository.get_depot(depot_code)
    location = depot["location"] if depot else "Unknown"
    await interaction.send(
        f"Checked out **{plane_type}** from **{depot['name'] if depot else depot_code}** ({location}).\n"
        f"Mission: **{mission}**\n"
        f"Good hunting."
    )
    await log_to_depot_thread(
        interaction.guild,
        depot_code,
        f"🛫 {interaction.user.mention} has taken out {article(plane_type)} **{plane_type}** for **{mission}**."
    )