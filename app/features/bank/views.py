import discord
from discord import ui
from app.libs.views.views import (
    AMOUNT_PATTERN, BaseModal, BaseView, FacilityModal, FacilitySelect, respond_or_followup
)
from app.features.bank.board import sync_stockpile_board  # Updated to sync the unified board
from app.features.bank.permissions import can_use_bank
from app.features.bank.repository import BankRepository

MAX_MODAL_FIELDS = 5  # Discord allows at most five inputs in one form


class CreateStockpileModal(FacilityModal, title="Add Officer Stockpile"):
    noun = "stockpile"
    name_label = "Stockpile Name"
    name_placeholder = "e.g. Officer Reserve"

    def is_duplicate(self, name: str) -> bool:
        return BankRepository.check_duplicate(name)

    async def create(self, interaction: discord.Interaction, name: str, code: str, location: str):
        BankRepository.add_stockpile(name, code, location, str(interaction.user.id))

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


class StockpileSelect(FacilitySelect):
    def __init__(self, action: str):
        self.action = action
        super().__init__(
            BankRepository.get_stockpiles(),
            placeholder="Choose a stockpile...",
            empty_label="No stockpiles available",
            empty_message="There are no stockpiles in the active war yet.",
        )

    async def on_pick(self, interaction: discord.Interaction, stockpile_id: int):
        stockpile = BankRepository.get_stockpile(stockpile_id)
        if not stockpile or stockpile["status"] != "ACTIVE":
            await respond_or_followup(interaction, "That stockpile no longer exists.")
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