"""Build entity lists for a Furbulous device (shared by platforms + dynamic add)."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.entity import Entity

from .analytics_entities import box_analytics_entities
from .binary_sensor import (
    FurbulousCatInBoxSensor,
    FurbulousChildLockBinarySensor,
    FurbulousConnectedSensor,
    FurbulousCoverOpenSensor,
    FurbulousDrawerNotInPlaceSensor,
    FurbulousNeedsCleaningSensor,
    FurbulousSleepModeSensor,
    FurbulousTrashDoorSensor,
    FurbulousWasteBinFullSensor,
)
from .button import FurbulousHandModeButton, FurbulousLitterResetButton
from .live_extra_sensors import (
    FurbulousCompletionStatusSensor,
    FurbulousDurationVsYesterdaySensor,
    FurbulousFirmwareSensor,
    FurbulousHandModeSensor,
    FurbulousUsesVsYesterdaySensor,
)
from .select import FurbulousCleanDelaySelect, FurbulousScreenModeSelect
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
    FurbulousEmptyConfirmSwitch,
    FurbulousFullAutoModeSwitch,
)


def sensor_entities_for_device(
    coordinator: Any,
    presence: Any,
    analytics: Any,
    device: dict,
) -> list[Entity]:
    """Sensors for one litter box (live + analytics)."""
    device_id = device.get("id")
    iotid = device.get("iotid")
    if device_id is None:
        return []
    entities: list[Entity] = [
        FurbulousLastActivitySensor(coordinator, device_id),
        FurbulousFirmwareSensor(coordinator, device_id),
    ]
    if iotid:
        entities.extend(
            [
                FurbulousCatWeightSensor(coordinator, device_id),
                FurbulousDailyUsesSensor(coordinator, device_id),
                FurbulousAverageDurationSensor(coordinator, device_id),
                FurbulousErrorSensor(presence, device_id),
                FurbulousHandModeSensor(presence, device_id),
                FurbulousCompletionStatusSensor(presence, device_id),
                FurbulousUsesVsYesterdaySensor(coordinator, device_id),
                FurbulousDurationVsYesterdaySensor(coordinator, device_id),
            ]
        )
        entities.extend(
            box_analytics_entities(coordinator, presence, analytics, device)
        )
    return entities


def binary_sensor_entities_for_device(
    coordinator: Any,
    presence: Any,
    device: dict,
    analytics: Any = None,
) -> list[Entity]:
    """Binary sensors for one device."""
    device_id = device.get("id")
    iotid = device.get("iotid")
    if device_id is None or not iotid:
        return []
    entities: list[Entity] = [
        FurbulousConnectedSensor(coordinator, device_id),
        FurbulousWasteBinFullSensor(presence, device_id),
        FurbulousCoverOpenSensor(presence, device_id),
        FurbulousDrawerNotInPlaceSensor(presence, device_id),
        FurbulousTrashDoorSensor(presence, device_id),
        FurbulousChildLockBinarySensor(coordinator, device_id),
        FurbulousSleepModeSensor(presence, device_id),
        FurbulousCatInBoxSensor(presence, device_id),
    ]
    if analytics is not None:
        entities.append(
            FurbulousNeedsCleaningSensor(coordinator, analytics, device)
        )
    return entities


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
        # Screen: use Screen mode select (DisplaySwitch), not masterSleepOnOff
        FurbulousChildLockSwitch(coordinator, api, device_id, iotid),
        FurbulousEmptyConfirmSwitch(coordinator, api, device_id, iotid),
    ]


def button_entities_for_device(
    coordinator: Any, api: Any, device: dict, analytics: Any = None
) -> list[Entity]:
    """Buttons for one device."""
    device_id = device.get("id")
    iotid = device.get("iotid")
    if device_id is None or not iotid:
        return []
    entities: list[Entity] = []
    from .entity_ids import (
        UID_CLEAN_NOW,
        UID_EMPTY_WASTE,
        UID_PAUSE_CLEANING,
        UID_RESUME_CLEANING,
        UID_SEAL_WASTE_BAG,
        box_uid,
    )

    for translation_key, slug, hand_mode, icon in (
        ("manual_clean", UID_CLEAN_NOW, 1, "mdi:broom"),
        ("pause_cleaning", UID_PAUSE_CLEANING, 4, "mdi:pause"),
        ("resume_cleaning", UID_RESUME_CLEANING, 5, "mdi:play"),
        ("empty", UID_EMPTY_WASTE, 2, "mdi:delete-empty"),
        ("pack", UID_SEAL_WASTE_BAG, 3, "mdi:package"),
    ):
        entities.append(
            FurbulousHandModeButton(
                coordinator,
                api,
                device_id,
                iotid,
                translation_key=translation_key,
                unique_id=box_uid(device_id, slug),
                hand_mode=hand_mode,
                icon=icon,
                analytics=analytics,
            )
        )
    if analytics is not None:
        entities.append(
            FurbulousLitterResetButton(
                coordinator, api, device_id, iotid, analytics
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
    return [
        FurbulousScreenModeSelect(coordinator, api, device_id, iotid),
        FurbulousCleanDelaySelect(coordinator, api, device_id, iotid),
    ]


def time_entities_for_device(
    coordinator: Any, api: Any, device: dict
) -> list[Entity]:
    """Writable Screen off / Quiet hours start–end times."""
    from .time import schedule_time_entities

    device_id = device.get("id")
    iotid = device.get("iotid")
    if device_id is None or not iotid:
        return []
    return list(schedule_time_entities(coordinator, api, device_id, iotid))
