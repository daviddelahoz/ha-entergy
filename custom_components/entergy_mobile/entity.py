"""Base entities for Entergy."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EntergyDataUpdateCoordinator


class EntergyEntity(CoordinatorEntity[EntergyDataUpdateCoordinator]):
    """Base Entergy entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EntergyDataUpdateCoordinator,
        entry_id: str,
        account_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._account_id = account_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, account_id)},
            name=f"Entergy Account {account_id}",
            manufacturer="Entergy",
            model="Entergy",
        )
