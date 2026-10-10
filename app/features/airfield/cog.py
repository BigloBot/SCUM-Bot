from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from app.features.airfield.panel import refresh_control_panel
from app.features.airfield.permissions import (
    AIRFIELD_AVIATOR_ROLE_KEY,
    can_use_airfield,
    is_airfield_admin,
    is_server_owner
)
from app.features.airfield.repository import AirfieldRepository
from app.features.airfield.threads import sync_war_threads
from app.features.airfield.views import (
    DepotFlightView,
    DepotManagementView,
    FlightReturnStatusView
)

def has_airfield_access():
    """
    Airfield commands: admins and holders of the airfield aviator role only (this role grants nothing elsewhere).
    Until an aviator role is set, only administrators can use them.
    """
    async def predicate(ctx: commands.Context):
        return ctx.guild is not None and can_use_airfield(ctx.author)
    return commands.check(predicate)

def has_airfield_admin():
    """Server owner, Discord administrators, and holders of the admin role the owner has set."""
    async def predicate(ctx: commands.Context):
        return ctx.guild is not None and is_airfield_admin(ctx.author)
    return commands.check(predicate)

def register(bot: commands.Bot):
    # Everything lives under /scum airfield. Discord only applies command visibility to top-level
    # commands, so /scum stays visible to everyone and permissions are enforced when a command runs.

    @bot.hybrid_group(name="scum", description="SCUM bot commands.")
    @commands.guild_only()
    async def scum(ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send("Try `/scum airfield` or `/scum war`.", ephemeral=True)

    @scum.group(name="airfield", description="Airfield depots, stockpiles and flights.")
    async def airfield(ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send("Try `/scum airfield panel`, `flight`, or `return`.", ephemeral=True)

    # ==================== AVIATOR COMMANDS ====================
    # The same controls live permanently in the controls channel (see `config`); these are shortcuts.
    @airfield.command(name="panel", description="Open the airfield control panel.")
    @commands.guild_only()
    @has_airfield_access()
    async def panel(ctx: commands.Context):
        forum_id = AirfieldRepository.get_config("forum_channel_id")
        if not forum_id:
            if is_airfield_admin(ctx.author):
                await ctx.send("No forum channel is set yet. Run `/scum airfield config` first.", ephemeral=True)
            else:
                await ctx.send("The forum channel hasn't been set up by an admin yet.", ephemeral=True)
            return

        forum_channel = ctx.guild.get_channel(int(forum_id))
        if not forum_channel or not isinstance(forum_channel, discord.ForumChannel):
            await ctx.send("The configured forum channel is no longer valid. An admin needs to run `/scum airfield config` again.", ephemeral=True)
            return

        war = AirfieldRepository.get_active_war()
        embed = discord.Embed(
            title="Airfield Control Panel",
            description=f"Active war: **War {war}**",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed, view=DepotManagementView(), ephemeral=True)

    @airfield.command(name="flight", description="Take an aircraft out of a depot.")
    @commands.guild_only()
    @has_airfield_access()
    async def flight(ctx: commands.Context):
        depots = AirfieldRepository.get_airfields()
        if not depots:
            await ctx.send("There are no depots in the active war yet.", ephemeral=True)
            return
        await ctx.send("Select the depot you are taking an aircraft from:", view=DepotFlightView(), ephemeral=True)

    @airfield.command(name="return", description="Log the outcome and air kills of your active flight.")
    @commands.guild_only()
    @has_airfield_access()
    async def flight_return(ctx: commands.Context):
        active_flight = AirfieldRepository.get_user_active_flight(str(ctx.author.id))
        if not active_flight:
            await ctx.send("You don't have an active flight to log.", ephemeral=True)
            return

        await ctx.send(
            f"Logging your **{active_flight['plane_type']}** flight. Select the outcome to open the kill sheet:",
            view=FlightReturnStatusView(active_flight),
            ephemeral=True
        )

    # ==================== WAR CONTROL ====================
    @scum.command(name="war", description="Show the active war, or switch to another war (admins only).")
    @app_commands.describe(number="War number to switch to. Leave empty to show the active war.")
    @commands.guild_only()
    @has_airfield_admin()
    async def war(ctx: commands.Context, number: Optional[int] = None):
        if number is None:
            await ctx.send(f"The active war is **War {AirfieldRepository.get_active_war()}**.", ephemeral=True)
            return

        if number < 1:
            await ctx.send("The war number must be 1 or higher.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)
        AirfieldRepository.set_active_war(number)

        # Every depot thread is brought in line with the new active war, so switching back to an
        # earlier war reopens exactly that war's threads and locks all the others.
        counts = await sync_war_threads(ctx.guild, number)
        message = (
            f"Active war set to **War {number}**. "
            f"Depot threads synced: {counts['changed']} updated, {counts['unchanged']} already correct."
        )
        problems = []
        if counts["failed"]:
            problems.append(f"{counts['failed']} could not be updated (check the bot's Manage Threads permission)")
        if counts["missing"]:
            problems.append(f"{counts['missing']} no longer exist in Discord")
        if problems:
            message += "\nNote: " + "; ".join(problems) + "."

        # Keep the active war shown on the permanent controls message current.
        await refresh_control_panel(ctx.guild)
        await ctx.send(message, ephemeral=True)

    # ==================== ADMIN CONFIG ====================
    @airfield.command(name="config", description="View or change airfield settings (admins only).")
    @app_commands.describe(
        forum="Forum channel where depot threads are created.",
        controls="Channel that holds the permanent control panel message.",
        aviator_role="Role allowed to use the airfield controls and commands.",
        admin_role="Role that counts as airfield admin, e.g. verified officer (server owner only)."
    )
    @commands.guild_only()
    @has_airfield_admin()
    async def config(
        ctx: commands.Context,
        forum: Optional[discord.ForumChannel] = None,
        controls: Optional[discord.TextChannel] = None,
        aviator_role: Optional[discord.Role] = None,
        admin_role: Optional[discord.Role] = None
    ):
        no_pings = discord.AllowedMentions.none()

        # With no options, just show the current settings.
        if all(option is None for option in (forum, controls, aviator_role, admin_role)):
            forum_id = AirfieldRepository.get_config("forum_channel_id")
            controls_id = AirfieldRepository.get_config("controls_channel_id")
            aviator_id = AirfieldRepository.get_config(AIRFIELD_AVIATOR_ROLE_KEY)
            admin_id = AirfieldRepository.get_config("admin_role_id")
            await ctx.send(
                "**Airfield settings**\n"
                f"Forum: {f'<#{forum_id}>' if forum_id else 'not set'}\n"
                f"Controls channel: {f'<#{controls_id}>' if controls_id else 'not set'}\n"
                f"Admin role: {f'<@&{admin_id}>' if admin_id else 'not set (Discord administrators only)'}\n"
                f"Aviator role: {f'<@&{aviator_id}>' if aviator_id else 'not set (admins only)'}\n"
                f"Active war: **War {AirfieldRepository.get_active_war()}** (change it with `/scum war`)",
                ephemeral=True,
                allowed_mentions=no_pings
            )
            return

        # Only the server owner may decide who counts as an admin, so an admin can't grant it onwards.
        # Checked before anything is changed, so a refused command changes nothing.
        if admin_role is not None:
            if not is_server_owner(ctx.author):
                await ctx.send("Only the server owner can set the admin role.", ephemeral=True)
                return
            if admin_role.is_default():
                await ctx.send("The admin role can't be @everyone.", ephemeral=True)
                return

        await ctx.defer(ephemeral=True)
        changes = []

        if admin_role is not None:
            AirfieldRepository.set_config("admin_role_id", str(admin_role.id))
            changes.append(f"Admin role set to {admin_role.mention}.")

        if forum is not None:
            AirfieldRepository.set_config("forum_channel_id", str(forum.id))
            changes.append(f"Forum set to {forum.mention}.")

        if aviator_role is not None:
            AirfieldRepository.set_config(AIRFIELD_AVIATOR_ROLE_KEY, str(aviator_role.id))
            changes.append(f"Aviator role set to {aviator_role.mention}.")

        # Post (or move) the permanent controls message.
        if controls is not None:
            result = await refresh_control_panel(ctx.guild, channel=controls)
            if result == "failed":
                changes.append(
                    f"Couldn't post the controls message in {controls.mention}. "
                    "Check that the bot can view the channel, send messages and embed links there."
                )
            else:
                changes.append(f"Controls message {result} in {controls.mention}.")

        await ctx.send("\n".join(changes), ephemeral=True, allowed_mentions=no_pings)
