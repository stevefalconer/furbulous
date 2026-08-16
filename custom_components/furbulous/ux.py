"""Cat-parent UX helpers + power-user automation attributes.

Primary entity *names* (via translations) are plain language for non-technical
cat lovers. Power users keep stable unique_ids, raw vendor codes, metric keys,
and domain bus events (see ``events.py`` / AnalyticsEngine).
"""
from __future__ import annotations

from typing import Any

# Audience roles for docs / attributes (not HA entity_category)
ROLE_PRIMARY = "primary"  # glanceable for any cat parent
ROLE_CHORE = "chore"  # bag / litter / empty workflows
ROLE_SETTING = "setting"  # configuration toggles
ROLE_POWER = "power"  # diagnostics, day-over-day, raw enums


def power_attrs(
    *,
    role: str,
    automation_hint: str | None = None,
    vendor_property: str | None = None,
    metric_key: str | None = None,
    raw: Any = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Attributes for advanced automations without cluttering the state name."""
    attrs: dict[str, Any] = {
        "audience": role,
    }
    if automation_hint:
        attrs["automation_hint"] = automation_hint
    if vendor_property:
        attrs["vendor_property"] = vendor_property
    if metric_key:
        attrs["metric_key"] = metric_key
    if raw is not None:
        attrs["raw_value"] = raw
    if extra:
        attrs.update(extra)
    return attrs
