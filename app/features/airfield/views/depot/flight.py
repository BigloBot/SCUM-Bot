import discord

from app.features.airfield.dashboard import refresh_controls
from app.features.airfield.repository import AirfieldRepository
from app.features.airfield.service import log_depot_event
from app.libs.discord.responses import Responder

# ==================== CONSTANTS & HELPERS ====================

MISSION_PRESETS = [
    "Large Ship Escort",
    "Heavy Bomber Escort",
    "Paratrooper Deployment",
    "Plane Transfer",
    "QRF",
    "Other"
]

def article(noun: str) -> str:
    """'a' or 'an' for the given (plain, unformatted) noun."""
    return "an" if noun[:1].lower() in "aeiou" else "a"


def join_natural(parts: list[str]) -> str:
    if len(parts) <= 2:
        return " and ".join(parts)
    return ", ".join(parts[:-1]) + f", and {parts[-1]}"


def quote(text: str) -> str:
    """Formats pilot-written text as a Discord block quote."""
    return "\n".join(f"> {line}" for line in text.strip().splitlines() if line.strip())


async def finish_flight(
        interaction: discord.Interaction, status: str, destination_id: int = None, cause: str = None
):
    """
    Closes the pilot's active flight and logs it in the depot thread(s). `status` is 'Returned' or 'Loss'.
    A returned Transport flight moves the aircraft to `destination_id`; any other return restocks the source depot.
    For a loss, `cause` is how the pilot says they died; it goes into the depot thread log.
    """
    flight = AirfieldRepository.get_user_active_flight(str(interaction.user.id))
    if not flight:
        await Responder(interaction).send("You don't have an active flight to log.")
        return

    try:
        AirfieldRepository.complete_flight(str(interaction.user.id), status, destination_id)
    except ValueError:
        await Responder(interaction).send("That destination depot is no longer active. Pick another one.")
        return

    plane_type = flight["plane_type"]
    plane = f"{article(plane_type)} **{plane_type}**"
    mention = interaction.user.mention
    source = AirfieldRepository.get_depot_by_id(flight["airfield_id"])
    source_name = source["name"] if source else "the depot"

    if status != "Returned":
        await Responder(interaction).send(f"Flight logged: **{plane_type}** lost.")
        entry = f"💥 {mention} has marked {plane} as lost."
        if cause and quote(cause):
            entry += f"\n**How they died:**\n{quote(cause)}"
        await log_depot_event(interaction.guild, flight["airfield_id"], entry)
        return

    if destination_id is not None and destination_id != flight["airfield_id"]:
        destination = AirfieldRepository.get_depot_by_id(destination_id)
        dest_name = destination["name"] if destination else "the destination depot"
        await Responder(interaction).send(f"Flight logged: **{plane_type}** transported from **{source_name}** to **{dest_name}**.")
        await log_depot_event(
            interaction.guild, flight["airfield_id"],
            f"🚚 {mention} has transported {plane} out to **{dest_name}**."
        )
        await log_depot_event(
            interaction.guild, destination_id,
            f"🚚 {mention} has transported {plane} in from **{source_name}**."
        )
        await refresh_controls(interaction.guild)
        return

    await Responder(interaction).send(f"Flight logged: **{plane_type}** returned to **{source_name}**.")
    await log_depot_event(
        interaction.guild, flight["airfield_id"], f"🛬 {mention} has returned {plane} to the stockpile."
    )
    await refresh_controls(interaction.guild)


async def checkout_and_log(interaction: discord.Interaction, airfield_id: int, plane_type: str, mission: str):
    user_id = str(interaction.user.id)
    success = AirfieldRepository.checkout_plane(airfield_id, plane_type, mission, user_id)
    if not success:
        await Responder(interaction).send(
            "You already have an active flight, or this depot is no longer active. "
            "Log your return first with **Log Return** on the airfield controls."
        )
        return

    depot = AirfieldRepository.get_depot_by_id(airfield_id)
    location = depot["location"] if depot else "Unknown"
    await Responder(interaction).send(
        f"Checked out **{plane_type}** from **{depot['name'] if depot else 'the depot'}** ({location}).\n"
        f"Mission: **{mission}**\n"
        f"Good hunting."
    )
    await log_depot_event(
        interaction.guild,
        airfield_id,
        f"🛫 {interaction.user.mention} has taken out {article(plane_type)} **{plane_type}** for **{mission}**."
    )
    await refresh_controls(interaction.guild)
