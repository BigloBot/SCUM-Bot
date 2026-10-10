import discord
from discord import app_commands
from discord.ext import commands
from app.features.airfield.repository import AirfieldRepository
from app.features.airfield.views import (
    DepotFlightView,
    DepotManagementView,
    FlightReturnStatusView
)

def has_aviator_role():
    """Checks if user has the configured aviator role or is an administrator."""
    async def predicate(ctx: commands.Context):
        if ctx.author.guild_permissions.administrator:
            return True
        role_id = AirfieldRepository.get_config("aviator_role_id")
        if not role_id:
            return True
        role = ctx.guild.get_role(int(role_id))
        return role and role in ctx.author.roles
    return commands.check(predicate)

def register(bot: commands.Bot):
    @bot.hybrid_group(name="airfield", description="Warden Airfield Logistics")
    async def airfield_group(ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send("Use `/airfield depot`, `/airfield log flight`, or `/airfield log return`.", ephemeral=True)

    # ==================== DEPOT CONTROL PANEL ====================
    @airfield_group.command(name="depot", description="Open interactive Warden Depot management control panel.")
    @has_aviator_role()
    async def airfield_depot(ctx: commands.Context):
        forum_id = AirfieldRepository.get_config("forum_channel_id")
        if not forum_id:
            if not ctx.author.guild_permissions.administrator:
                await ctx.send("⚠️ Forum channel not configured by an admin yet.", ephemeral=True)
                return
            await ctx.send("⚠️ Forum channel not configured! Please run `/airfield forum-set` first.", ephemeral=True)
            return

        forum_channel = ctx.guild.get_channel(int(forum_id))
        if not forum_channel or not isinstance(forum_channel, discord.ForumChannel):
            await ctx.send("❌ Configured forum channel is invalid.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🛡️ Warden Airfield & Depot Control Center",
            description="Use the interactive controls below to create new depots, add aircraft stock, view details, or delete/archive depots.",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed, view=DepotManagementView(forum_channel), ephemeral=True)

    # ==================== LOG GROUP ====================
    @airfield_group.group(name="log", description="Pilot flight logging operations")
    async def log_group(ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send("Use `/airfield log flight` or `/airfield log return`.", ephemeral=True)

    @log_group.command(name="flight", description="Take out an aircraft from a depot.")
    @has_aviator_role()
    async def log_flight(ctx: commands.Context):
        depots = AirfieldRepository.get_airfields()
        if not depots:
            await ctx.send("⚠️ No depots registered for the active war.", ephemeral=True)
            return
        await ctx.send("Select the airfield depot you are taking a plane out from:", view=DepotFlightView(), ephemeral=True)

    @log_group.command(name="return", description="Log the outcome and structured air kills of your active flight.")
    @has_aviator_role()
    async def log_return(ctx: commands.Context):
        flight = AirfieldRepository.get_user_active_flight(str(ctx.author.id))
        if not flight:
            await ctx.send("⚠️ You do not have an active checked-out flight to return.", ephemeral=True)
            return

        # Step 1: Offer Returned / Loss buttons cleanly
        await ctx.send(
            f"✈️ **Logging Return for Active Flight:** `{flight['plane_type']}`\n"
            f"Select aircraft outcome to open kill sheet:",
            view=FlightReturnStatusView(flight),
            ephemeral=True
        )

    # ==================== ADMIN CONFIGURATION ====================
    @airfield_group.command(name="forum-set", description="Set the Discord Forum channel for depot threads.")
    @app_commands.default_permissions(administrator=True)
    async def forum_set(ctx: commands.Context, channel: discord.ForumChannel):
        AirfieldRepository.set_config("forum_channel_id", str(channel.id))
        await ctx.send(f"✅ Forum channel successfully set to **{channel.name}**.", ephemeral=True)

    @airfield_group.command(name="role-set", description="Set the private aviator role required for flights.")
    @app_commands.default_permissions(administrator=True)
    async def role_set(ctx: commands.Context, role: discord.Role):
        AirfieldRepository.set_config("aviator_role_id", str(role.id))
        await ctx.send(f"✅ Aviator role successfully set to **{role.name}**.", ephemeral=True)

    # ==================== WAR MANAGEMENT ====================
    @bot.hybrid_group(name="war", description="War configuration and archival")
    @app_commands.default_permissions(administrator=True)
    async def war_group(ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            active = AirfieldRepository.get_active_war()
            await ctx.send(f"🛡️ Current active war is **War {active}**.", ephemeral=True)

    @war_group.command(name="set", description="Set active war number and automatically archive/unarchive depot threads.")
    @app_commands.default_permissions(administrator=True)
    async def war_set(ctx: commands.Context, war_number: int):
        await ctx.defer(ephemeral=True)
        old_war = AirfieldRepository.get_active_war()
        AirfieldRepository.set_active_war(war_number)

        all_depots = AirfieldRepository.get_all_war_airfields()
        for depot in all_depots:
            if not depot["thread_id"]:
                continue
            try:
                thread = ctx.bot.get_channel(int(depot["thread_id"]))
                if thread:
                    if depot["war_number"] == war_number and depot["status"] == "ACTIVE":
                        await thread.edit(archived=False, reason=f"Switched to active War {war_number}")
                    elif depot["war_number"] == old_war:
                        await thread.edit(archived=True, locked=True, reason=f"Archiving completed War {old_war}")
            except Exception:
                pass

        await ctx.followup.send(f"✅ Active war updated to **War {war_number}**. Depot threads automatically synced and archived/unarchived!", ephemeral=True)