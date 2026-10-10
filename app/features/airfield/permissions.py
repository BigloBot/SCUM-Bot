import discord
from app.features.airfield.repository import AirfieldRepository


def is_server_owner(member) -> bool:
    return isinstance(member, discord.Member) and member.guild.owner_id == member.id


def _has_configured_role(member: discord.Member, config_key: str) -> bool:
    role_id = AirfieldRepository.get_config(config_key)
    return bool(role_id) and any(role.id == int(role_id) for role in member.roles)


def is_airfield_admin(member) -> bool:
    """
    The server owner, Discord administrators, and holders of the admin role the server owner has set
    (e.g. a verified officer role) are airfield admins.
    """
    if not isinstance(member, discord.Member):
        return False
    if is_server_owner(member) or member.guild_permissions.administrator:
        return True
    return _has_configured_role(member, "admin_role_id")


def member_can_fly(member) -> bool:
    """Airfield admins, or members holding the aviator role (admins only until an aviator role is set)."""
    if not isinstance(member, discord.Member):
        return False
    return is_airfield_admin(member) or _has_configured_role(member, "aviator_role_id")
