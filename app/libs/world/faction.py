from enum import StrEnum


class Faction(StrEnum):
    Warden = "Warden"
    Colonial = "Colonial"

    @property
    def enemy(self) -> "Faction":
        return Faction.Colonial if self is Faction.Warden else Faction.Warden