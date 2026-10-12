"""
The kill types pilots can report, in dropdown order.
Loaded from config.yaml (features.airfield.colonial_planes).

`key` is what a kill report stores, so never change a key once reports exist (it would orphan their history);
`label` is the name shown on the dropdown and the kill board, and `description` is the dropdown's hint.
"""
from collections.abc import Mapping, Sequence
from app.core.config import config, PlaneType

# KillType alias for backwards compatibility
KillType = PlaneType


class _KillTypesSequence(Sequence):
    """Dynamic view of configured colonial planes in list/sequence order."""
    def __iter__(self):
        return iter(config.features.airfield.colonial_planes)

    def __len__(self):
        return len(config.features.airfield.colonial_planes)

    def __getitem__(self, index):
        return config.features.airfield.colonial_planes[index]

    def __repr__(self):
        return repr(config.features.airfield.colonial_planes)


class _KillTypesMapping(Mapping):
    """Dynamic view of configured colonial planes mapped by key."""
    def __getitem__(self, key):
        return config.colonial_planes_by_key[key]

    def __iter__(self):
        return iter(config.colonial_planes_by_key)

    def __len__(self):
        return len(config.colonial_planes_by_key)

    def __contains__(self, key):
        return key in config.colonial_planes_by_key

    def __repr__(self):
        return repr(config.colonial_planes_by_key)

    def get(self, key, default=None):
        return config.colonial_planes_by_key.get(key, default)


KILL_TYPES = _KillTypesSequence()
KILL_TYPES_BY_KEY = _KillTypesMapping()
