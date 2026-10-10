from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from app.features.airfield.repository import AirfieldRepository
from app.features.airfield.threads import sync_war_threads
from app.features.airfield.views import (
    DepotFlightView,
    DepotManagementView,
    FlightReturnStatusView
)

def has_aviator_role():
    """
    Only server administrators and members with the configured aviator role may run flight commands.
    Until an aviator role is set, only administrators can use them.
    """
    async def predicate(ctx: commands.Context):
        if ctx.guild is None:
            return False
        if ctx.author.guild_permissions.administrator:
            return True
        role_id = AirfieldRepository.get_config("aviator_role_id")
        if not role_id:
            return False
        return any(role.id == int(role_id) for role in ctx.author.roles)
    return commands.check(predicate)

def register(bot: commands.Bot):
    # Discord only applies command permissions to top-level commands, so every command is top-level.
    # Admin commands are hidden from everyone else (default_permissions) and also enforced when run.

    # ==================== AVIATOR COMMANDS ====================
    @bot.hybrid_command(name="depot", description="Open the depot control panel.")
    @commands.guild_only()
    @has_aviator_role()
    async def depot(ctx: commands.Context):
        forum_id = AirfieldRepository.get_config("forum_channel_id")
        if not forum_id:
            if ctx.author.guild_permissions.administrator:
                await ctx.send("No forum channel is set yet. Run `/forum` first.", ephemeral=True)
            else:
                await ctx.send("The forum channel hasn't been set up by an admin yet.", ephemeral=True)
            return

        forum_channel = ctx.guild.get_channel(int(forum_id))
        if not forum_channel or not isinstance(forum_channel, discord.ForumChannel):
            await ctx.send("The configured forum channel is no longer valid. An admin needs to run `/forum` again.", ephemeral=True)
            return

        war = AirfieldRepository.get_active_war()
        embed = discord.Embed(
            title="Depot Control Panel",
            description=(
                f"Active war: **War {war}**\n"
                "Create depots, add aircraft stock, view stockpiles, or delete depots."
            ),
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed, view=DepotManagementView(forum_channel), ephemeral=True)

    @bot.hybrid_command(name="flight", description="Take an aircraft out of a depot.")
    @commands.guild_only()
    @has_aviator_role()
    async def flight(ctx: commands.Context):
        depots = AirfieldRepository.get_airfields()
        if not depots:
            await ctx.send("There are no depots in the active war yet.", ephemeral=True)
            return
        await ctx.send("Select the depot you are taking an aircraft from:", view=DepotFlightView(), ephemeral=True)

    @bot.hybrid_command(name="return", description="Log the outcome and air kills of your active flight.")
    @commands.guild_only()
    @has_aviator_role()
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

    # ==================== ADMIN COMMANDS ====================
    @bot.hybrid_command(name="forum", description="Set the forum channel used for depot threads.")
    @app_commands.default_permissions(administrator=True)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def forum(ctx: commands.Context, channel: discord.ForumChannel):
        AirfieldRepository.set_config("forum_channel_id", str(channel.id))
        await ctx.send(f"Forum channel set to **{channel.name}**.", ephemeral=True)

    @bot.hybrid_command(name="role", description="Set the aviator role that can run flight commands.")
    @app_commands.default_permissions(administrator=True)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def role(ctx: commands.Context, role: discord.Role):
        AirfieldRepository.set_config("aviator_role_id", str(role.id))
        await ctx.send(f"Aviator role set to **{role.name}**.", ephemeral=True)

    @bot.hybrid_command(name="war", description="Show the active war, or switch to another war number.")
    @app_commands.default_permissions(administrator=True)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def war(ctx: commands.Context, war_number: Optional[int] = None):
        if war_number is None:
            active = AirfieldRepository.get_active_war()
            await ctx.send(f"The active war is **War {active}**.", ephemeral=True)
            return

        if war_number < 1:
            await ctx.send("The war number must be 1 or higher.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)
        AirfieldRepository.set_active_war(war_number)

        # Every depot thread is brought in line with the new active war, so switching back to an
        # earlier war reopens exactly that war's threads and locks all the others.
        counts = await sync_war_threads(ctx.guild, war_number)

        message = (
            f"Active war set to **War {war_number}**. "
            f"Depot threads synced: {counts['changed']} updated, {counts['unchanged']} already correct."
        )
        problems = []
        if counts["failed"]:
            problems.append(f"{counts['failed']} could not be updated (check the bot's Manage Threads permission)")
        if counts["missing"]:
            problems.append(f"{counts['missing']} no longer exist in Discord")
        if problems:
            message += "\nNote: " + "; ".join(problems) + "."
        await ctx.send(message, ephemeral=True)
