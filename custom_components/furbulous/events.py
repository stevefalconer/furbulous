"""Home Assistant bus events for power-user automations.

Cat parents use entity states (Last cat, Needs emptying, …). Advanced users can
trigger automations on these domain events without scraping every sensor.

Events (domain ``furbulous`` prefix is applied by the bus as event type):

- ``furbulous_visit_ended`` — cat left the box (pet_name, weight_g, duration_s, …)
- ``furbulous_waste_full`` — waste bag became full
- ``furbulous_waste_cleared`` — full condition cleared
- ``furbulous_bag_replaced`` — Empty closed a bag cycle
- ``furbulous_litter_reset`` — user marked litter refilled
- ``furbulous_pack`` — Seal waste bag pressed / recorded
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

EVENT_VISIT_ENDED = f"{DOMAIN}_visit_ended"
EVENT_WASTE_FULL = f"{DOMAIN}_waste_full"
EVENT_WASTE_CLEARED = f"{DOMAIN}_waste_cleared"
EVENT_BAG_REPLACED = f"{DOMAIN}_bag_replaced"
EVENT_LITTER_RESET = f"{DOMAIN}_litter_reset"
EVENT_PACK = f"{DOMAIN}_pack"


def emit_event(
    hass: HomeAssistant | None,
    event_type: str,
    data: dict[str, Any],
) -> None:
    """Fire a domain event if HA is available (no-op in pure unit tests)."""
    if hass is None:
        return
    try:
        payload = dict(data)
        payload.setdefault("domain", DOMAIN)
        hass.bus.async_fire(event_type, payload)
    except Exception:  # pylint: disable=broad-except
        _LOGGER.debug("Failed to emit %s", event_type, exc_info=True)
