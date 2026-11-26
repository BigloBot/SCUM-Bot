"""Matching free text typed by a person against a fixed list of choices."""
from collections.abc import Sequence

from app.libs.errors import Refused

MAX_SUGGESTIONS = 5


def match_choice(text: str, choices: Sequence[str], *, noun: str = "option") -> str:
    """
    The choice `text` means. An exact match (ignoring case) wins, then a single choice that starts with the text,
    then a single choice that contains it. Raises Refused when nothing matches or several equally good ones do.
    """
    needle = text.strip().casefold()
    if not needle:
        raise Refused(f"Enter a {noun}.")

    for tier in (
        lambda c: c.casefold() == needle,
        lambda c: c.casefold().startswith(needle),
        lambda c: needle in c.casefold(),
    ):
        found = [c for c in choices if tier(c)]
        if len(found) == 1:
            return found[0]
        if len(found) > 1:
            options = ", ".join(found[:MAX_SUGGESTIONS])
            raise Refused(f"'{text.strip()}' could be more than one {noun}: {options}")
    raise Refused(f"No {noun} matches '{text.strip()}'.")
