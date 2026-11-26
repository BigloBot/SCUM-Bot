"""Matching free text typed by a person against a fixed list of choices."""
import unicodedata
from collections.abc import Sequence

from app.libs.errors import Refused

MAX_SUGGESTIONS = 5


def _fold(text: str) -> str:
    """Lowercase with accents removed, so "onyx" finds "Ónyx"."""
    decomposed = unicodedata.normalize("NFKD", text.strip().casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def match_choice(text: str, choices: Sequence[str], *, noun: str = "option") -> str:
    """
    The choice `text` means. An exact match (ignoring case) wins, then a single choice that starts with the text,
    then a single choice that contains it. Raises Refused when nothing matches or several equally good ones do.
    """
    needle = _fold(text)
    if not needle:
        raise Refused(f"Enter a {noun}.")

    for tier in (
        lambda c: _fold(c) == needle,
        lambda c: _fold(c).startswith(needle),
        lambda c: needle in _fold(c),
    ):
        found = [c for c in choices if tier(c)]
        if len(found) == 1:
            return found[0]
        if len(found) > 1:
            options = ", ".join(found[:MAX_SUGGESTIONS])
            raise Refused(f"'{text.strip()}' could be more than one {noun}: {options}")
    raise Refused(f"No {noun} matches '{text.strip()}'.")
