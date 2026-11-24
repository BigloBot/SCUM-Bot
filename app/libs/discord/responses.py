import asyncio
import logging

import discord

logger = logging.getLogger(__name__)

INTERNAL_ERROR = "An internal error occurred. Please try again"

DEFAULT_AUTO_DELETE_SECONDS = 60.0

_background_tasks: set[asyncio.Task] = set()


async def _delete_later(message: discord.Message, delay: float) -> None:
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except discord.NotFound:
        pass
    except Exception:
        logger.warning("Could not auto-delete a reply.", exc_info=True)

class Responder:
    """Replies to one interactiom, hiding the response-vs-followup state."""

    def __init__(self, interaction: discord.Interaction):
        self.interaction = interaction

    async def send(
            self,
            content: str | None = None,
            *,
            ephemeral: bool = True,
            delete_after: float | None = DEFAULT_AUTO_DELETE_SECONDS,
            **kwargs
    ):
        interaction = self.interaction
        kwargs.setdefault("allowed_mentions", discord.AllowedMentions.none())
        view = kwargs.get("view")
        if delete_after is not None and view is not None and view.timeout:
            delete_after = max(delete_after, view.timeout)

        try:
            if interaction.response.is_done():
                message = await interaction.followup.send(
                    content, ephermeral=ephemeral, wait=bool(delete_after), **kwargs
                )
            else:
                await interaction.response.send_message(content, ephemeral=ephemeral, **kwargs)
                message = await interaction.original_response() if delete_after else None
        except: discord.HTTPException:
            logger.error("Could not send an interaction response.", exc_info=True)
            return None

        if delete_after and message is not None:
            task = asyncio.create_task(_delete_later(message, delete_after))
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)
        return message

    async def error(self):
        try:
            await self.send(INTERNAL_ERROR)
        except Exception:
            logger.error("Could not deliver the internal error message to the user.", exc_info=True)