import discord

from app.libs.content.text import clip

MAX_SELECT_OPTIONS = 25
MAX_OPTION_LABEL = 100
MAX_OPTION_DESCRIPTION = 100
MAX_PLACEHOLDER = 150

MAX_MODAL_TITLE = 45
MAX_MODAL_INPUTS = 5
MAX_INPUT_LABEL = 45
MAX_INPUT_PLACEHOLDER = 100

MAX_THREAD_NAME = 100

def fit_option(option: discord.SelectOption, *, default: bool | None = None) -> discord.SelectiOption:
    return discord.SelectOption(
        label=clip(option.label, MAX_OPTION_LABEL),
        value=option.value,
        description=clip(option.description, MAX_OPTION_DESCRIPTION) if option.description else None,
        emoji=option.emoji,
        default=option.default if default is None else default,
    )