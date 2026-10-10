import discord
from app.features.airfield.repository import AirfieldRepository

# Settings keys are namespaced per feature, so a role configured for one feature can never be picked up
# by another. A new feature defines its own role setting and its own check; it does not reuse these.
AIRFIELD_AVIATOR_ROLE_KEY = "airfield.aviator_role_id"

# The admin role is deliberately server-wide: it says who runs the bot, not who may use one feature.
ADMIN_ROLE_KEY = "admin_role_id"


def is_server_owner(member) -> bool:
    return isinstance(member, discord.Member) and member.guild.owner_id == member.id


def _has_configured_role(member: discord.Member, config_key: str) -> bool:
    role_id = AirfieldRepository.get_config(config_key)
    return bool(role_id) and any(role.id == int(role_id) for role in member.roles)


def is_airfield_admin(member) -> bool:
    """
    The server owner, Discord administrators, and holders of the admin role the server owner has set
    (e.g. a verified officer role) are admins.
    """
    if not isinstance(member, discord.Member):
        return False
    if is_server_owner(member) or member.guild_permissions.administrator:
        return True
    return _has_configured_role(member, ADMIN_ROLE_KEY)


def can_use_airfield(member) -> bool:
    """
    Access to the airfield depot and flight features only: admins, or holders of the airfield aviator role
    (admins only until that role is set). The aviator role grants nothing outside the airfield feature.
    """
    if not isinstance(member, discord.Member):
        return False
    return is_airfield_admin(member) or _has_configured_role(member, AIRFIELD_AVIATOR_ROLE_KEY)
