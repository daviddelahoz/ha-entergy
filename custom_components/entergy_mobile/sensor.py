"""Sensors for Entergy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import get_coordinator
from .const import ATTR_ACCOUNT_ID, ATTR_IS_ESTIMATED, ATTR_LAST_INTERVAL, ATTR_LAST_UPDATE, DOMAIN
from .coordinator import EntergyDataUpdateCoordinator
from .entity import EntergyEntity


@dataclass(frozen=True, kw_only=True)
class EntergySensorEntityDescription(SensorEntityDescription):
    """Description for Entergy sensors."""

    key: str


SENSORS: tuple[EntergySensorEntityDescription, ...] = (
    EntergySensorEntityDescription(
        key="total_import_kwh",
        name="Imported Energy Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
    ),
    EntergySensorEntityDescription(
        key="total_export_kwh",
        name="Exported Energy Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
    ),
    EntergySensorEntityDescription(
        key="latest_hour_net_kwh",
        name="Latest Hour Net Usage",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=3,
    ),
    EntergySensorEntityDescription(
        key="latest_hour_import_kwh",
        name="Latest Hour Import",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=3,
    ),
    EntergySensorEntityDescription(
        key="latest_hour_export_kwh",
        name="Latest Hour Export",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=3,
    ),
    EntergySensorEntityDescription(
        key="latest_hour_cost",
        name="Latest Hour Cost",
        native_unit_of_measurement="$",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
    ),
    EntergySensorEntityDescription(
        key="latest_day_net_kwh",
        name="Latest Day Net Usage",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=3,
    ),
    EntergySensorEntityDescription(
        key="latest_day_import_kwh",
        name="Latest Day Import",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=3,
    ),
    EntergySensorEntityDescription(
        key="latest_day_export_kwh",
        name="Latest Day Export",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=3,
    ),
    EntergySensorEntityDescription(
        key="latest_day_cost",
        name="Latest Day Cost",
        native_unit_of_measurement="$",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
    ),
    EntergySensorEntityDescription(
        key="last_7_days_net_kwh",
        name="Last 7 Days Net Usage",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=3,
    ),
    EntergySensorEntityDescription(
        key="last_7_days_cost",
        name="Last 7 Days Cost",
        native_unit_of_measurement="$",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
    ),
    EntergySensorEntityDescription(
        key="month_to_date_net_kwh",
        name="Month-to-Date Net Usage",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=3,
    ),
    EntergySensorEntityDescription(
        key="month_to_date_cost",
        name="Month-to-Date Cost",
        native_unit_of_measurement="$",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
    ),
    EntergySensorEntityDescription(
        key="tracked_interval_count",
        name="Tracked Hourly Intervals",
        icon="mdi:counter",
    ),
    EntergySensorEntityDescription(
        key="latest_hour_timestamp",
        name="Latest Hour Timestamp",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator: EntergyDataUpdateCoordinator = get_coordinator(hass, entry)
    account_id = entry.data["account_id"]

    async_add_entities(
        EntergySensor(coordinator, entry.entry_id, account_id, description)
        for description in SENSORS
    )


class EntergySensor(EntergyEntity, SensorEntity):
    """Entergy sensor."""

    entity_description: EntergySensorEntityDescription

    def __init__(
        self,
        coordinator: EntergyDataUpdateCoordinator,
        entry_id: str,
        account_id: str,
        description: EntergySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry_id, account_id)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{account_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return sensor value."""
        value = (self.coordinator.data or {}).get(self.entity_description.key)
        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP and isinstance(value, str):
            return dt_util.parse_datetime(value)
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return useful metadata."""
        data = self.coordinator.data or {}
        attrs: dict[str, Any] = {
            ATTR_ACCOUNT_ID: self._account_id,
            ATTR_LAST_UPDATE: data.get("last_update"),
        }

        if data.get("latest_hour_timestamp"):
            attrs[ATTR_LAST_INTERVAL] = data.get("latest_hour_timestamp")
        if data.get("latest_hour_estimated") is not None:
            attrs[ATTR_IS_ESTIMATED] = data.get("latest_hour_estimated")
        if self.entity_description.key.startswith("latest_day"):
            attrs["latest_day"] = data.get("latest_day")
        if self.entity_description.key.startswith("month_to_date"):
            attrs["month_to_date_date"] = data.get("month_to_date_date")

        return attrs
