"""
A whole form in one Discord message: a few dropdowns and a button, with nothing saved until the button is pressed.

Describe the form instead of subclassing views and selects:

    form = FormView(
        [
            FormField("plane", "an aircraft", "Choose an aircraft...", options),
            FormField("qty", "a quantity", "How many?", simple_options(range(1, 11)), default="1", convert=int),
        ],
        submit=save,                  # async (interaction, values) -> text that replaces the form
        submit_label="Add Stock",
        done=log,                     # optional: async (interaction, values), runs after the reply
        actions=[FormAction("Custom...", open_modal)],   # optional extra buttons
    )
    await interaction.response.send_message("Fill this in:", view=form, ephemeral=True)

A field without a default has to be chosen before any button works; a field with one starts preselected.
`values` handed to the callbacks maps each field key to its converted choice.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any

import discord
from discord import ui

from app.libs.views.views import MAX_SELECT_OPTIONS, BaseView, respond_or_followup

logger = logging.getLogger(__name__)

MAX_FORM_FIELDS = 4   # a message holds 5 rows of components and the buttons need one
MAX_FORM_ACTIONS = 4  # extra buttons next to the submit button (a row holds 5)

FormValues = dict[str, Any]


class FormError(Exception):
    """Raised by a form callback to refuse the submission: the message is shown privately and the form stays open."""


def simple_options(values: Iterable[Any]) -> list[discord.SelectOption]:
    """Dropdown options whose label and value are both the text of each item."""
    return [discord.SelectOption(label=str(v), value=str(v)) for v in values]


@dataclass(frozen=True)
class FormField:
    """
    One dropdown. `label` completes "Choose {label} first." when it is left empty. `default` is the value to
    preselect (None: the person has to choose). `convert` turns the chosen value text into what callbacks receive.
    """
    key: str
    label: str
    placeholder: str
    options: Sequence[discord.SelectOption]
    default: str | None = None
    convert: Callable[[str], Any] = str


@dataclass(frozen=True)
class FormAction:
    """An extra button beside the submit button. Its handler runs only once every required field is chosen."""
    label: str
    handler: Callable[[discord.Interaction, FormValues], Awaitable[None]]
    style: discord.ButtonStyle = discord.ButtonStyle.secondary
    emoji: str | None = None


def _copy_options(options: Sequence[discord.SelectOption], selected: str | None) -> list[discord.SelectOption]:
    """Fresh option objects (the same list can back several forms) with `selected` marked as chosen."""
    return [
        discord.SelectOption(
            label=o.label, value=o.value, description=o.description, emoji=o.emoji, default=(o.value == selected)
        )
        for o in options
    ]


class _FormSelect(ui.Select):
    def __init__(self, form_field: FormField, row: int):
        self.form_field = form_field
        super().__init__(
            placeholder=form_field.placeholder, min_values=1, max_values=1, row=row,
            options=_copy_options(form_field.options, form_field.default),
        )

    async def callback(self, interaction: discord.Interaction):
        chosen = self.values[0]
        self.view.values[self.form_field.key] = self.form_field.convert(chosen)
        # Redrawing the message with the choice marked keeps the dropdown showing it.
        for option in self.options:
            option.default = option.value == chosen
        await interaction.response.edit_message(view=self.view)


class FormView(BaseView):
    def __init__(
            self,
            fields: Sequence[FormField],
            *,
            submit: Callable[[discord.Interaction, FormValues], Awaitable[str]],
            submit_label: str = "Submit",
            submit_emoji: str | None = None,
            done: Callable[[discord.Interaction, FormValues], Awaitable[None]] | None = None,
            actions: Sequence[FormAction] = (),
            timeout: float = 300.0,
    ):
        if not 1 <= len(fields) <= MAX_FORM_FIELDS:
            raise ValueError(f"a form needs 1 to {MAX_FORM_FIELDS} fields, got {len(fields)}")
        if len(actions) > MAX_FORM_ACTIONS:
            raise ValueError(f"a form holds at most {MAX_FORM_ACTIONS} extra buttons, got {len(actions)}")
        keys = [f.key for f in fields]
        if len(set(keys)) != len(keys):
            raise ValueError("form field keys must be unique")
        for f in fields:
            if not 1 <= len(f.options) <= MAX_SELECT_OPTIONS:
                raise ValueError(f"field '{f.key}' needs 1 to {MAX_SELECT_OPTIONS} options, got {len(f.options)}")
            if f.default is not None and f.default not in [o.value for o in f.options]:
                raise ValueError(f"field '{f.key}' default {f.default!r} is not one of its options")

        super().__init__(timeout=timeout)
        self.fields = list(fields)
        self.values: FormValues = {}
        self._submit_handler = submit
        self._done_handler = done

        for row, f in enumerate(self.fields):
            if f.default is not None:
                self.values[f.key] = f.convert(f.default)
            self.add_item(_FormSelect(f, row))

        button_row = len(self.fields)
        submit_button = ui.Button(
            label=submit_label, emoji=submit_emoji, style=discord.ButtonStyle.green, row=button_row)
        submit_button.callback = self._on_submit
        self.add_item(submit_button)
        for action in actions:
            button = ui.Button(label=action.label, emoji=action.emoji, style=action.style, row=button_row)
            button.callback = self._action_callback(action)
            self.add_item(button)

    def missing_field(self) -> FormField | None:
        """The first field still waiting for a choice, if any."""
        return next((f for f in self.fields if f.key not in self.values), None)

    async def _ready(self, interaction: discord.Interaction) -> bool:
        """True when every field has a choice; otherwise tells the person what is missing."""
        missing = self.missing_field()
        if missing is None:
            return True
        await respond_or_followup(interaction, f"Choose {missing.label} first.")
        return False

    def _action_callback(self, action: FormAction):
        async def callback(interaction: discord.Interaction):
            if await self._ready(interaction):
                await action.handler(interaction, dict(self.values))
        return callback

    async def _on_submit(self, interaction: discord.Interaction):
        if not await self._ready(interaction):
            return
        values = dict(self.values)
        try:
            text = await self._submit_handler(interaction, values)
        except FormError as error:
            await respond_or_followup(interaction, str(error))
            return

        self.stop()
        await interaction.response.edit_message(content=text, view=None)
        if self._done_handler is not None:
            await self._done_handler(interaction, values)
