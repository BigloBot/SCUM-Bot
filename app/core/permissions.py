"""Server-wide permission rules. Feature-specific roles live in each feature's own permissions module."""
import discord
from discord.ext import commands
from app.core.config import config
from app.core.settings import get_setting

# The admin role is deliberately server-wide: it says who runs the bot, not who may use one feature.
ADMIN_ROLE_KEY = "admin_role_id"


def is_server_owner(member) -> bool:
    return isinstance(member, discord.Member) and member.guild.owner_id == member.id


def has_configured_role(member: discord.Member, config_key: str) -> bool:
    role_id = get_setting(config_key)
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


def has_admin():
    """Command check: admins only."""
    async def predicate(ctx: commands.Context):
        return ctx.guild is not None and is_admin(ctx.author)
    return commands.check(predicate)
