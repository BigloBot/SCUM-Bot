"""
The kill types pilots can report, in dropdown order. This is configuration, not data: edit this list and
redeploy to add, rename or reorder them.

`key` is what a kill report stores, so never change a key once reports exist (it would orphan their history);
`label` is the name shown on the dropdown and the kill board, and `description` is the dropdown's hint.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class KillType:
    key: str
    label: str
    description: str


KILL_TYPES: list[KillType] = [
    KillType("toxot", "Toxot-902", "Toxot-902 “Blind Silver” (Fighter)"),
    KillType("harpy", "Harpy", "Daimon aK-5 “Harpy” (Heavy Fighter)"),
    KillType("myrmidon", "Myrmidon", "Mergo-4 “Myrmidon” (Dive Bomber)"),
    KillType("pegasus", "Pegasus", "V-5b Pegasus (Paratrooper Plane)"),
    KillType("tzykalia", "Tzykalia", "Tzykalia (Heavy Bomber)"),
]

KILL_TYPES_BY_KEY: dict[str, KillType] = {t.key: t for t in KILL_TYPES}
