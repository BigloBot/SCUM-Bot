"""The /scum root command and the commands that span every feature."""
import logging
from collections.abc import Sequence
from typing import Optional

import discord
from discord import app_commands

from app.core import settings
from app.core.config import reload_config
from app.core.permissions import ADMIN_ROLE_KEY, has_admin, is_server_owner
from app.libs.discord.format import PANEL_RESULT_LABELS, role_or
from app.libs.discord.responses import Responder
from app.libs.feature import Feature
from app.libs.world.faction import Faction

logger = logging.getLogger(__name__)

def build_root(features: Sequence[Feature]) -> app_commands.Group:
    """/scum with cross-feature commands, and each feature's own commands attached as subcommands."""
    scum = app_commands.Group(name="scum", description="SCUM bot commands", guild_only=True)

    @scum.command(name="help", description="What SCUMBot can do.")
    async def help_command(interaction: discord.Interaction):
        lines = [f"**/scum {f.name.lower()}**: {f.help}" for f in features]
        lines.append("**/scum config**: active war and admin role (admins only).")
        lines.append("**/scum refresh**: repost or refresh every control panel (admins only).")
        await Responder(interaction).send("\n".join(lines))

    @scum.command(name="config", description="View or change server-wide settings (admins only).")
    @app_commands.describe(
        war="Active war number, shared by every feature. Switching it locks other wars' depot threads and reopens this war's.",
        faction="The faction being played this war",
        admin_role="Role that counts as an admin for every feature, e.g. verified officer (server owner only)."
    )
    @has_admin()
    async def config(
            interaction: discord.Interaction,
            war: Optional[int] = None,
            faction: Optional[Faction] = None,
            admin_role: Optional[discord.Role] = None,
    ):
        reply = Responder(interaction)
        if war is None and faction is None and admin_role is None:
            await reply.send(
                "**Server settings**\n"
                f"Active war: **War {settings.get_active_war()}**\n"
                f"Faction: **{settings.get_faction()}**\n"
                f"Admin role: {role_or(settings.get_setting(ADMIN_ROLE_KEY), 'not set (Discord admins only)')}"
            )
            return

        # Only the server owner may decide who counts as an admin, so an admin can't grant it onwards.
        # Checked before anything is changed, so a refused command changes nothing.
        if admin_role is not None:
            if not is_server_owner(interaction.user):
                await reply.send("Only the server owner can set the admin role.")
                return
            if admin_role.is_default():
                await reply.send("The admin role can't be @everyone.")
                return
        if war is not None and war < 1:
            await reply.send("The war number must be 1 or higher.")
            return
        await interaction.response.defer(ephemeral=True, thinking=True)

        lines = []
        if admin_role is not None:
            settings.set_setting(ADMIN_ROLE_KEY, str(admin_role.id))
            lines.append(f"Admin role set to {admin_role.mention}.")

        target_war = war if war is not None else settings.get_active_war()
        if war is not None:
            settings.set_active_war(war)
            lines.append(f"Active war set to **War {war}**.")

        if faction is not None:
            settings.set_faction(faction, target_war)
            lines.append(f"Faction set to **{faction}** for War {target_war}.")

        if war is not None:
            for feature in features:
                if feature.on_war_change is not None:
                    lines.extend(await feature.on_war_change(interaction.guild, war))
        elif faction is not None:
            for feature in features:
                if feature.resync is not None and await feature.resync(interaction.guild) == "failed":
                    lines.append(f"The {feature.name} panels could not be refreshed. Check permissions.")

        await reply.send("\n".join(lines))

    @scum.command(name="refresh", description="Reload the config and resync the control panel messages (admins only).")
    @has_admin()
    async def refresh(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        config_line = "Config: reloaded"
        try:
            reload_config()
        except Exception as error:
            logger.error("Could not reload config.yaml.", exc_info=True)
            reason = (str(error).splitlines() or [type(error).__name__])[0][:200]
            config_line = f"Config: **not reloaded**, still using the previous one ({reason})"

        lines = ["**Resync**"]
        for feature in features:
            if feature.resync is not None:
                lines.append(f"{feature.name}: {PANEL_RESULT_LABELS[await feature.resync(interaction.guild)]}")
        lines.append(config_line)
        await Responder(interaction).send("\n".join(lines))

    for feature in features:
        feature.register(scum)
    return scum
