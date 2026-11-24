from pydantic import ConfigDict, Field, PrivateAttr, model_validator

from app.libs.discord.limits import MAX_SELECT_OPTIONS
from app.libs.models import Strict
from app.libs.world.faction import Faction

from app.core.settings import set_faction


class UnitType(Strict):
    model_config = ConfigDict(extra="forbid", froxen=True)

    key: str
    label: str
    description: str

class Vehicles(Strict):

    planes: list[UnitType] = Field(default_factory=list)
    ships: list[UnitType] = Field(default_factory=list) # LS

    def all(self) -> list[UnitType]:
        return [unit for category in type(self).model_fields for unit in getattr(self, category)]

class Roster(Strict):
    vehicles: vehicles = Field(default_factory=Vehicles)

    def units(self, category: str) -> list[UnitType]:
        return list(getattr(self.vehicles, category))

class Forces(Strict):

    factions: dict[Faction, Roster] = Field(default_factory=dict)
    shared: Roster = Field(default_factory=Roster)

    _by_key: dict[str, UnitType] = PrivateAttr(default_factory=dict)

    def model_post_init(self, context) -> None:
        self._by_key = {u_key: u for roster in self._rosters() for u in roster.vehicles.all()}

    @model_validator
    def _check(self) -> "Forces":
        keys = [u.key for roster in self._rosters() for u in roster.vehicles.all()]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate 'key' found in world config")
        for faction in self.factions:
            count = len(self.planes(faction))
            if count > MAX_SELECT_OPTIONS:
                raise ValueError(
                    f"{faction} has {count} planes including shared; a dropdown can hold most {MAX_SELECT_OPTIONS}"
                )
        return self

    def _rosters(self) -> list[Roster]:
        return[*self.factions.values(), self.shared]

    def own(self, faction: Faction, category: str) -> list[UnitType]:
        roster = self.factions.get(faction)
        return roster.units(category) if roster else []

    def units(self, faction: Faction, category: str) -> list[UnitType]:
        return [*self.own(faction, category), *self.shared.units(category)]

    def planes(self, faction: Faction) -> list[UnitType]:
        return self.units(faction, "planes")

    def ships(self, faction: Faction) -> list[UnitType]:
        return self.units(faction, "ships")

    def enemy_planes(self, faction: Faction) -> list[UnitType]:
        return self.own(faction.enemy, "planes")

    def unit_label(self, key: str) -> str:
        unit = self._by_key.get(key)
        return unit.label if unit else key
