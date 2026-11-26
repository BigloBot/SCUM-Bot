"""Small text helpers shared by every feature."""


def clip(text: str, limit: int) -> str:
    """`text` cut to at most `limit` characters, ending in an ellipsis when something was removed."""
    if limit < 1:
        return ""
    if len(text) <= limit:
        return text
    if limit == 1:
        return "…"
    return text[: limit - 1].rstrip() + "…"
