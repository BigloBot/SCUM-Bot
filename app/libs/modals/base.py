"""Shared Discord modal bases and validation patterns."""
from __future__ import annotations

from abc import ABC, abstractmethod
import logging

import discord
from discord import ui

from app.libs.views.views import PASSCODE_PATTERN, respond_or_followup, send_internal_error

logger = logging.getLogger(__name__)


class BaseModal(ui.Modal):
    """Modal base with the application's standard interaction error handling."""

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await send_internal_error(interaction)


class FacilityModal(BaseModal, ABC):
    """Reusable name, passcode, and location form for a facility-like record."""

    noun = "facility"
    name_label = "Name"
    name_placeholder = ""
    location_label = "Location"
    location_placeholder = "e.g. Callahan's Passage"

    def __init__(self):
        super().__init__()
        self.facility_name = ui.TextInput(
            label=self.name_label, placeholder=self.name_placeholder, required=True, max_length=40)
        self.facility_code = ui.TextInput(
            label="Passcode (6 digits)", placeholder="e.g. 123456", required=True, min_length=6, max_length=6)
        self.facility_location = ui.TextInput(
            label=self.location_label, placeholder=self.location_placeholder, required=True, max_length=40)
        for field in (self.facility_name, self.facility_code, self.facility_location):
            self.add_item(field)

    @abstractmethod
    def is_duplicate(self, name: str) -> bool:
        """Return whether this facility name is already active."""

    @abstractmethod
    async def create(self, interaction: discord.Interaction, name: str, code: str, location: str) -> None:
        """Persist the validated facility and send the deferred interaction response."""

    async def on_submit(self, interaction: discord.Interaction):
        name = self.facility_name.value.strip()
        code = self.facility_code.value.strip()
        location = self.facility_location.value.strip()

        if not name or not location:
            await respond_or_followup(interaction, f"The {self.noun} name and location can't be empty.")
            return
        if not PASSCODE_PATTERN.fullmatch(code):
            await respond_or_followup(interaction, "The passcode must be exactly 6 digits (0-9).")
            return
        if self.is_duplicate(name):
            await respond_or_followup(interaction, f"A {self.noun} with that name is already active in this war.")
            return
