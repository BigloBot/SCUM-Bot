import discord
from app.core.permissions import has_configured_role, is_admin

# Namespaced to this feature: the bank officer role grants nothing outside the bank.
BANK_OFFICER_ROLE_KEY = "bank.officer_role_id"


def can_use_bank(member) -> bool:
    """Bank features only: admins, or holders of the bank officer role (admins only until it is set)."""
    if not isinstance(member, discord.Member):
        return False
    return is_admin(member) or has_configured_role(member, BANK_OFFICER_ROLE_KEY)
