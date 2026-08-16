"""Build entity lists for a Furbulous device (shared by platforms + dynamic add)."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.entity import Entity

from .binary_sensor import (
    FurbulousCatInBoxSensor,
    FurbulousChildLockBinarySensor,
    FurbulousConnectedSensor,
    FurbulousSleepModeSensor,
    FurbulousWasteBinFullSensor,
)
from .button import FurbulousHandModeButton
from .select import FurbulousCleanDelaySelect
from .sensor import (
    FurbulousAverageDurationSensor,
    FurbulousCatWeightSensor,
    FurbulousDailyUsesSensor,
    FurbulousErrorSensor,
    FurbulousLastActivitySensor,
)
from .switch import (
    FurbulousChildLockSwitch,
    FurbulousDNDSwitch,
    FurbulousFullAutoModeSwitch,
)


def sensor_entities_for_device(coordinator: Any, device: dict) -> list[Entity]:
    """Sensors for one device (normal coordinator)."""
    device_id = device.get("id")
    iotid = device.get("iotid")
    if device_id is None:
        return []
    entities: list[Entity] = [FurbulousLastActivitySensor(coordinator, device_id)]
    if iotid:
        entities.extend(
            [
                FurbulousCatWeightSensor(coordinator, device_id),
                FurbulousDailyUsesSensor(coordinator, device_id),
                FurbulousAverageDurationSensor(coordinator, device_id),
                FurbulousErrorSensor(coordinator, device_id),
            ]
        )
    return entities


def binary_sensor_entities_for_device(
    coordinator: Any, presence: Any, device: dict
) -> list[Entity]:
    """Binary sensors for one device."""
    device_id = device.get("id")
    iotid = device.get("iotid")
    if device_id is None or not iotid:
        return []
    return [
        FurbulousConnectedSensor(coordinator, device_id),
        FurbulousWasteBinFullSensor(coordinator, device_id),
        FurbulousChildLockBinarySensor(coordinator, device_id),
        FurbulousSleepModeSensor(coordinator, device_id),
        FurbulousCatInBoxSensor(presence, device_id),
    ]


def switch_entities_for_device(
    coordinator: Any, api: Any, device: dict
) -> list[Entity]:
    """Switches for one device."""
    device_id = device.get("id")
    iotid = device.get("iotid")
    if device_id is None or not iotid:
        return []
    return [
        FurbulousFullAutoModeSwitch(coordinator, api, device_id, iotid),
        FurbulousDNDSwitch(coordinator, api, device_id, iotid),
        FurbulousChildLockSwitch(coordinator, api, device_id, iotid),
    ]


def button_entities_for_device(
    coordinator: Any, api: Any, device: dict
) -> list[Entity]:
    """Buttons for one device."""
    device_id = device.get("id")
    iotid = device.get("iotid")
    if device_id is None or not iotid:
        return []
    entities: list[Entity] = []
    for translation_key, unique_suffix, hand_mode, icon in (
        ("manual_clean", "manual_clean", 1, "mdi:broom"),
        ("pause_cleaning", "pause_clean", 4, "mdi:pause"),
        ("resume_cleaning", "resume_clean", 5, "mdi:play"),
        ("empty", "dump", 2, "mdi:delete-empty"),
        ("pack", "pack", 3, "mdi:package"),
    ):
        entities.append(
            FurbulousHandModeButton(
                coordinator,
                api,
                device_id,
                iotid,
                translation_key=translation_key,
                unique_id=f"{iotid}_{unique_suffix}",
                hand_mode=hand_mode,
                icon=icon,
            )
        )
    return entities


def select_entities_for_device(
    coordinator: Any, api: Any, device: dict
) -> list[Entity]:
    """Select entities for one device."""
    device_id = device.get("id")
    iotid = device.get("iotid")
    if device_id is None or not iotid:
        return []
    return [FurbulousCleanDelaySelect(coordinator, api, device_id, iotid)]
