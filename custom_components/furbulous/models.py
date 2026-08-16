"""Shared runtime types for one config entry."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .coordinator import FurbulousDataUpdateCoordinator, FurbulousPresenceCoordinator
    from .furbulous_api import FurbulousCatAPI


@dataclass(slots=True)
class FurbulousRuntimeData:
    """One API client + two coordinators per config entry (no global caches)."""

    api: FurbulousCatAPI
    coordinator: FurbulousDataUpdateCoordinator
    presence_coordinator: FurbulousPresenceCoordinator
