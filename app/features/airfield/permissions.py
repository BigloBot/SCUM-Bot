import discord
from app.core.permissions import has_configured_role, is_admin

# Namespaced to this feature, so a role set here can never grant access in another feature.
# A new feature defines its own role setting and its own check; it does not reuse this one.
AIRFIELD_AVIATOR_ROLE_KEY = "airfield.aviator_role_id"


def can_use_airfield(member) -> bool:
    """
    Access to the airfield depot and flight features only: admins, or holders of the airfield aviator role
    (admins only until that role is set). The aviator role grants nothing outside the airfield feature.
    """
    if not isinstance(member, discord.Member):
        return False
    return is_admin(member) or has_configured_role(member, AIRFIELD_AVIATOR_ROLE_KEY)
