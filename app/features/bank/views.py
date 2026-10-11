import re
import discord
from discord import ui
from app.core.ui import PASSCODE_PATTERN, BaseModal, BaseView
from app.features.bank.board import sync_stockpile_board  # Updated to sync the unified board
from app.features.bank.permissions import can_use_bank
from app.features.bank.repository import BankRepository

# A whole number of up to 9 digits (matches the form field's max length).
AMOUNT_PATTERN = re.compile(r"[0-9]{1,9}")
MAX_MODAL_FIELDS = 5  # Discord allows at most five inputs in one form


class CreateStockpileModal(BaseModal, title="Add Officer Stockpile"):
    stockpile_name = ui.TextInput(label="Stockpile Name", placeholder="e.g. Officer Reserve", required=True, max_length=40)
    stockpile_code = ui.TextInput(label="Passcode (6 digits)", placeholder="e.g. 123456", required=True, min_length=6, max_length=6)
    stockpile_location = ui.TextInput(label="Location", placeholder="e.g. Callahan's Passage", required=True, max_length=40)

    async def on_submit(self, interaction: discord.Interaction):
        name = self.stockpile_name.value.strip()
        code = self.stockpile_code.value.strip()
        location = self.stockpile_location.value.strip()

        if not name or not location:
            await interaction.response.send_message("The stockpile name and location can't be empty.", ephemeral=True)
            return
        if not PASSCODE_PATTERN.fullmatch(code):
            await interaction.response.send_message("The passcode must be exactly 6 digits (0-9).", ephemeral=True)
            return

        if BankRepository.check_duplicate(name):
            await interaction.response.send_message(
                "A stockpile with that name is already active in this war.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        stockpile_id = BankRepository.add_stockpile(name, code, location, str(interaction.user.id))

        # Refresh the single unified stockpile board message
        await sync_stockpile_board(interaction.guild)

        await interaction.followup.send(
            f"Stockpile **{name}** added. Use Update Stock to enter how much it holds.", ephemeral=True
        )


class UpdateStockModal(BaseModal):
    """One field per tracked material, pre-filled with the current amount. Whatever is entered becomes the new total."""

    def __init__(self, stockpile_id: int, stockpile_name: str, balances: dict[str, int]):
        super().__init__(title=f"Update {stockpile_name}"[:45])
        self.stockpile_id = stockpile_id
        self.fields_by_resource: dict[str, ui.TextInput] = {}
        for label, amount in list(balances.items())[:MAX_MODAL_FIELDS]:
            field = ui.TextInput(label=label, default=str(amount), required=True, max_length=9)
            self.add_item(field)
            self.fields_by_resource[label] = field

    async def on_submit(self, interaction: discord.Interaction):
        amounts = {}
        for label, field in self.fields_by_resource.items():
            raw = field.value.strip().replace(",", "")
            if not AMOUNT_PATTERN.fullmatch(raw):
                await interaction.response.send_message(
                    f"**{label}** must be a whole number, 0 or higher.", ephemeral=True
                )
                return
            amounts[label] = int(raw)

        stockpile = BankRepository.get_stockpile(self.stockpile_id)
        if not stockpile or stockpile["status"] != "ACTIVE":
            await interaction.response.send_message("That stockpile no longer exists.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        changes = BankRepository.set_balances(self.stockpile_id, amounts, str(interaction.user.id))
        if changes:
            # Refresh the single unified stockpile board message
            await sync_stockpile_board(interaction.guild)
            lines = "\n".join(f"{label}: {old:,} to {new:,}" for label, old, new in changes)
            await interaction.followup.send(f"Updated **{stockpile['name']}**.\n{lines}", ephemeral=True)
        else:
            await interaction.followup.send("No changes. Those are already the current amounts.", ephemeral=True)


class StockpileSelect(ui.Select):
    def __init__(self, action: str):
        self.action = action
        stockpiles = BankRepository.get_stockpiles()
        options = [
            discord.SelectOption(label=s["name"], value=str(s["id"]), description=f"Location: {s['location']}"[:100])
            for s in stockpiles[:25]
        ]
        if not options:
            options = [discord.SelectOption(label="No stockpiles available", value="NONE")]
        super().__init__(placeholder="Choose a stockpile...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "NONE":
            await interaction.response.send_message("There are no stockpiles in the active war yet.", ephemeral=True)
            return

        stockpile = BankRepository.get_stockpile(int(self.values[0]))
        if not stockpile or stockpile["status"] != "ACTIVE":
            await interaction.response.send_message("That stockpile no longer exists.", ephemeral=True)
            return

        if self.action == "update":
            balances, _ = BankRepository.get_summary(stockpile["id"])
            await interaction.response.send_modal(UpdateStockModal(stockpile["id"], stockpile["name"], balances))
        elif self.action == "delete":
            await interaction.response.defer(ephemeral=True)
            BankRepository.delete_stockpile(stockpile["id"])

            # Refresh the single unified stockpile board message to remove it
            await sync_stockpile_board(interaction.guild)

            await interaction.followup.send(
                f"Stockpile **{stockpile['name']}** deleted. Its history is kept for reports.", ephemeral=True
            )


class BankControlView(BaseView):
    """
    The bank control panel. Persistent: fixed custom_ids and no timeout, so the buttons keep working
    across bot restarts.
    """
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if can_use_bank(interaction.user):
            return True
        await interaction.response.send_message("You don't have permission to use these controls.", ephemeral=True)
        return False

    @ui.button(label="Add Stockpile", style=discord.ButtonStyle.green, custom_id="bank:add_stockpile")
    async def add_stockpile(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(CreateStockpileModal())

    @ui.button(label="Update Stock", style=discord.ButtonStyle.primary, custom_id="bank:update_stock")
    async def update_stock(self, interaction: discord.Interaction, button: ui.Button):
        view = BaseView()
        view.add_item(StockpileSelect("update"))
        await interaction.response.send_message("Select the stockpile to update:", view=view, ephemeral=True)

    @ui.button(label="Delete Stockpile", style=discord.ButtonStyle.danger, custom_id="bank:delete_stockpile")
    async def delete_stockpile(self, interaction: discord.Interaction, button: ui.Button):
        view = BaseView()
        view.add_item(StockpileSelect("delete"))
        await interaction.response.send_message("Select the stockpile to delete:", view=view, ephemeral=True)