"""Unit tests for dynamic device entity registration helper."""
from __future__ import annotations

from custom_components.furbulous.helpers import async_add_devices_listener


class FakeCoordinator:
    """Minimal coordinator stub."""

    def __init__(self) -> None:
        self.data: dict | None = {"devices": []}
        self._listeners: list = []

    def async_add_listener(self, listener):
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def notify(self) -> None:
        for listener in list(self._listeners):
            listener()


def test_listener_adds_only_new_devices():
    """Entities are built once per device id."""
    coordinator = FakeCoordinator()
    known: set = set()
    added: list = []

    def async_add_entities(entities, update_before_add=False):
        added.extend(entities)

    def build(device):
        return [f"entity-{device['id']}"]

    listener = async_add_devices_listener(
        coordinator,  # type: ignore[arg-type]
        async_add_entities,
        build,
        known,
    )

    coordinator.data = {
        "devices": [
            {"id": 1, "iotid": "a", "name": "Box A"},
            {"id": 2, "iotid": "b", "name": "Box B"},
        ]
    }
    listener()
    assert sorted(added) == ["entity-1", "entity-2"]
    assert known == {1, 2}

    # Same devices again — no duplicates
    added.clear()
    listener()
    assert added == []

    # New device appears
    coordinator.data = {
        "devices": [
            {"id": 1, "iotid": "a", "name": "Box A"},
            {"id": 2, "iotid": "b", "name": "Box B"},
            {"id": 3, "iotid": "c", "name": "Box C"},
        ]
    }
    listener()
    assert added == ["entity-3"]
    assert known == {1, 2, 3}


def test_listener_skips_devices_without_id():
    """Devices missing id are ignored."""
    coordinator = FakeCoordinator()
    known: set = set()
    added: list = []

    listener = async_add_devices_listener(
        coordinator,  # type: ignore[arg-type]
        lambda ents, update_before_add=False: added.extend(ents),
        lambda d: [d],
        known,
    )
    coordinator.data = {"devices": [{"iotid": "x"}, {"id": 9, "iotid": "y"}]}
    listener()
    assert known == {9}
    assert len(added) == 1
