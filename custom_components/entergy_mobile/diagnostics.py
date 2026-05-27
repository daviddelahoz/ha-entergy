"""Diagnostics support for Entergy."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import get_coordinator

TO_REDACT = {
    CONF_USERNAME,
    CONF_PASSWORD,
    "access_token",
    "accessToken",
    "Authorization",
    "clientId",
    "raw",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = get_coordinator(hass, entry)
    data = {
        "entry": {
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "last_update_success": coordinator.last_update_success,
        "coordinator_data": coordinator.data,
    }
    return async_redact_data(data, TO_REDACT)
