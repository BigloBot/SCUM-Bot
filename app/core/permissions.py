"""Server-wide permission rules. Feature-specific roles live in each feature's own permissions module."""
from collections.abc import Callable

import discord
from discord import app_commands

from app.core.config import config
from app.core.settings import get_setting

# Global Admin Role
ADMIN_ROLE_KEY = "admin_role_id"


def is_server_owner(member) -> bool:
    return isinstance(member, discord.Member) and member.guild.owner_id == member.id


def has_configured_role(member: discord.Member, setting_key: str) -> bool:
    role_id = get_setting(setting_key)
    return bool(role_id) and any(role.id == int(role_id) for role in member.roles)


def is_admin(member) -> bool:
    """
    The server owner, Discord administrators, configured bot owners, and holders of the admin role
    the server owner has set (e.g. a verified officer role) are admins.
    """
    if not isinstance(member, discord.Member):
        return False
    if is_server_owner(member) or member.guild_permissions.administrator:
        return True
    if member.id in config.bot.owner_ids:
        return True
    return has_configured_role(member, ADMIN_ROLE_KEY)


def feature_role(role_key: str) -> Callable[[object], bool]:
    """Access to one feature"""
    def allowed(member) -> bool:
        return is_admin(member) or (isinstance(member, discord.Member) and has_configured_role(member, role_key))
    return allowed


def has_admin():
    """Command check: admins only."""
    async def predicate(interaction: discord.Interaction) -> bool:
        return interaction.guild is not None and is_admin(interaction.user)
    return app_commands.check(predicate)
