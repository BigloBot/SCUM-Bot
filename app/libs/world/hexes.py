from pydantic import RootModel, model_validator

from app.libs.content.matching import match_choice
from app.libs.errors import Refused

class Hexes(RootModel[list[str]]):
    """The map's hex-based regions"""

    @model_validator(mode="after")
    def _unique(self) -> "Hexes":
        lowered = [h.casefold() for h in self.root]
        if len(lowered) != len(set(lowered)):
            raise ValueError("Duplicate entry found in world.hexes config")
        return self

    def match(self, text: str) -> str:
        if not self.root:
            raise Refused("No hexes are configured")
        return match_choice(text, self.root, noun="hex")

    def order(self, name: str) -> int:
        try:
            return self.root.index(name)
        except ValueError:
            return len(self.root)