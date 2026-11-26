"""Bank panels: the control panel with war-wide totals, and the board of every active stockpile under it."""
import discord

from app.core import settings
from app.features.bank.repository import BankRepository
from app.libs.discord.panels import PanelResult, PanelStack, PersistentPanel

# These keys name settings that already exist in deployed databases ("bank.controls_message_id" and
# "bank.board_message_id"), so panels posted before the move to PanelStack keep being edited in place.
BANK_CHANNEL_KEY = "bank.channel_id"


def build_controls_embed() -> discord.Embed:
    war = settings.get_active_war()
    embed = discord.Embed(
        title="Bank Control Panel",
        description=(
            f"Active war: **War {war}**\n\n"
            "Add officer stockpiles and keep their rare material counts up to date. "
            "All active stockpiles are summarized in the board below. "
            "Replies are only visible to you."
        ),
        color=discord.Color.blue()
    )
    totals, count = BankRepository.get_totals(war)
    lines = "\n".join(f"{label}: {amount:,}" for label, amount in totals.items()) or "No materials tracked."
    embed.add_field(
        name=f"Total across all stockpiles ({count} active)",
        value=f"```yaml\n{lines}\n```",
        inline=False
    )
    return embed


def build_board_embed() -> discord.Embed:
    war = settings.get_active_war()
    stockpiles = BankRepository.get_stockpiles()
    active_stockpiles = [
        s for s in stockpiles
        if s["status"] == "ACTIVE" and s["war_number"] == war
    ]

    embed = discord.Embed(
        title=f"📦 Active Officer Stockpiles (War {war})",
        color=discord.Color.gold()
    )

    if not active_stockpiles:
        embed.description = "No active stockpiles for this war yet. Use the **Add Stockpile** button above to create one."
        return embed

    for stockpile in active_stockpiles:
        balances, _ = BankRepository.get_summary(stockpile["id"])

        balance_lines = [f"  • {label}: {amount:,}" for label, amount in balances.items()]
        materials_text = "\n".join(balance_lines) if balance_lines else "  • No items recorded"

        field_value = (
            f"🔑 **Code:** `{stockpile['code']}` | 📍 **Location:** {stockpile['location']}\n"
            f"\n"
            f"**Materials:**\n"
            f"{materials_text}\n"
            f"\n"
        )
        embed.add_field(name=f"📦 {stockpile['name']}", value=field_value, inline=False)

    embed.set_footer(text="Updated")
    embed.timestamp = discord.utils.utcnow()
    return embed


def build_controls_view() -> discord.ui.View:
    from app.features.bank.views import BankControlView  # imported here to keep modules decoupled
    return BankControlView()


controls_panel = PersistentPanel(
    "bank.controls", build_embed=build_controls_embed, build_view=build_controls_view, name="bank controls",
)
board_panel = PersistentPanel("bank.board", build_embed=build_board_embed, name="bank stockpile board")

# Controls first, board below. If either has to be posted again the other follows, keeping that order.
bank_stack = PanelStack(
    BANK_CHANNEL_KEY,
    [controls_panel, board_panel],
    get_setting=settings.get_setting,
    set_setting=settings.set_setting,
)


async def sync_stockpile_board(guild: discord.Guild) -> PanelResult:
    """Updates the controls (war-wide totals) and the board in place after any stockpile change."""
    return await bank_stack.sync(guild)


async def rebuild_board(guild: discord.Guild, channel: discord.TextChannel | None = None) -> PanelResult:
    """Posts the controls and the board again, in `channel` (or the channel already set)."""
    return await bank_stack.rebuild(guild, channel)
