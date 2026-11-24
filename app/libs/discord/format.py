import discord

from app.libs.discord.panels import PanelResult

PANEL_RESULT_LABELS: dict[PanelResult, str] = {
    "updated": "refreshed",
    "posted": "reposted",
    "no_channel": "not set up",
    "failed": "failed (chck permissions)"
}

def channel_or(channel_id: str | None, fallback: str = "not set") -> str:
    return f"<#{channel_id}>" if channel_id else fallback

def role_or(role_id: str | None, fallback: str = "not set (admins only)") -> str:
    return f"<@&{role_id}>" if role_id else fallback

def panel_posted_line(result: PanelResult, channel: discord.abc.GuildChannel, what: str) -> str:
    if result == "failed":
        return (
            f"Could not post the {what} in {channel.mention} (check permissions)."
        )
    return f"{what[:1].upper()}{what[1:]} {result} in {channel.mention}"