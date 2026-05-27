"""Data coordinator and parsing for Entergy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import EntergyApiClient, EntergyApiError, EntergyAuthError
from .const import DEFAULT_SCAN_INTERVAL_SECONDS, DOMAIN, STORAGE_KEY_PREFIX, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class HourlyUsage:
    """One hourly usage interval."""

    timestamp: str
    usage: float
    cost: float | None
    is_estimated: bool


def _parse_iso_z(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _utcnow() -> datetime:
    now = dt_util.utcnow()
    if now.tzinfo is None:
        return now.replace(tzinfo=UTC)
    return now.astimezone(UTC)


def _safe_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _get_path(data: dict[str, Any], *keys: str) -> Any:
    cur: Any = data
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _sum_usage(items: list[Any]) -> float:
    total = 0.0
    for item in items:
        if not isinstance(item, dict):
            continue
        value = _safe_float(item.get("usage"))
        if value is not None:
            total += value
    return round(total, 3)


def _sum_cost(items: list[Any]) -> float:
    total = 0.0
    for item in items:
        if not isinstance(item, dict):
            continue
        value = _safe_float(item.get("cost"))
        if value is not None:
            total += value
    return round(total, 2)


def extract_hourly_usage(payload: dict[str, Any]) -> list[HourlyUsage]:
    """Extract hourly usage records from the weeklyusage schema."""
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return []

    daily_electric = _safe_list(_get_path(data, "daily", "electric"))
    records: list[HourlyUsage] = []

    for day in daily_electric:
        if not isinstance(day, dict):
            continue
        for hourly in _safe_list(day.get("hourly")):
            if not isinstance(hourly, dict):
                continue
            timestamp = hourly.get("date")
            usage = _safe_float(hourly.get("usage"))
            if not isinstance(timestamp, str) or usage is None:
                continue
            cost = _safe_float(hourly.get("cost"))
            records.append(
                HourlyUsage(
                    timestamp=timestamp,
                    usage=usage,
                    cost=cost,
                    is_estimated=bool(hourly.get("isEstimated", False)),
                )
            )

    return sorted(records, key=lambda x: x.timestamp)


def parse_usage_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Parse the Entergy weeklyusage payload."""
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return {}

    monthly_electric = _safe_list(_get_path(data, "monthly", "electric"))
    weekly_electric = _safe_list(_get_path(data, "weekly", "electric"))
    hourly_records = extract_hourly_usage(payload)

    latest_hour: HourlyUsage | None = hourly_records[-1] if hourly_records else None

    latest_day = None
    latest_day_records: list[HourlyUsage] = []
    if hourly_records:
        latest_day = _parse_iso_z(hourly_records[-1].timestamp).date()
        latest_day_records = [
            record
            for record in hourly_records
            if _parse_iso_z(record.timestamp).date() == latest_day
        ]

    latest_month_entry = monthly_electric[-1] if monthly_electric else {}
    month_to_date_usage = None
    month_to_date_cost = None
    month_to_date_date = None
    if isinstance(latest_month_entry, dict):
        month_to_date_usage = _safe_float(latest_month_entry.get("usage"))
        month_to_date_cost = _safe_float(latest_month_entry.get("cost"))
        month_to_date_date = latest_month_entry.get("date")

    latest_import = max(latest_hour.usage, 0.0) if latest_hour else None
    latest_export = abs(min(latest_hour.usage, 0.0)) if latest_hour else None

    latest_day_net = round(sum(record.usage for record in latest_day_records), 3)
    latest_day_import = round(sum(max(record.usage, 0.0) for record in latest_day_records), 3)
    latest_day_export = round(sum(abs(min(record.usage, 0.0)) for record in latest_day_records), 3)
    latest_day_cost = round(
        sum(record.cost for record in latest_day_records if record.cost is not None),
        2,
    )

    return {
        "last_7_days_net_kwh": _sum_usage(weekly_electric),
        "last_7_days_cost": _sum_cost(weekly_electric),
        "latest_day": latest_day.isoformat() if latest_day else None,
        "latest_day_net_kwh": latest_day_net if latest_day_records else None,
        "latest_day_import_kwh": latest_day_import if latest_day_records else None,
        "latest_day_export_kwh": latest_day_export if latest_day_records else None,
        "latest_day_cost": latest_day_cost if latest_day_records else None,
        "latest_hour_timestamp": latest_hour.timestamp if latest_hour else None,
        "latest_hour_net_kwh": round(latest_hour.usage, 3) if latest_hour else None,
        "latest_hour_import_kwh": round(latest_import, 3) if latest_import is not None else None,
        "latest_hour_export_kwh": round(latest_export, 3) if latest_export is not None else None,
        "latest_hour_cost": round(latest_hour.cost, 2) if latest_hour and latest_hour.cost is not None else None,
        "latest_hour_estimated": latest_hour.is_estimated if latest_hour else None,
        "month_to_date_net_kwh": round(month_to_date_usage, 3) if month_to_date_usage is not None else None,
        "month_to_date_cost": round(month_to_date_cost, 2) if month_to_date_cost is not None else None,
        "month_to_date_date": month_to_date_date,
        "hourly_records": hourly_records,
    }


class EntergyUsageStore:
    """Persistent cumulative energy store for Energy dashboard sensors."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store = Store[dict[str, Any]](
            hass,
            STORAGE_VERSION,
            f"{STORAGE_KEY_PREFIX}_{entry_id}",
        )
        self._data: dict[str, Any] = {}

    async def async_load(self) -> None:
        loaded = await self._store.async_load()
        self._data = loaded if isinstance(loaded, dict) else {}
        self._data.setdefault("total_import_kwh", 0.0)
        self._data.setdefault("total_export_kwh", 0.0)
        self._data.setdefault("intervals", {})

    async def async_process(self, records: list[HourlyUsage]) -> dict[str, Any]:
        intervals: dict[str, Any] = self._data.setdefault("intervals", {})
        changed = False

        for record in records:
            existing = intervals.get(record.timestamp)
            import_kwh = round(max(record.usage, 0.0), 6)
            export_kwh = round(abs(min(record.usage, 0.0)), 6)

            if existing is None:
                self._data["total_import_kwh"] = round(
                    float(self._data.get("total_import_kwh", 0.0)) + import_kwh,
                    6,
                )
                self._data["total_export_kwh"] = round(
                    float(self._data.get("total_export_kwh", 0.0)) + export_kwh,
                    6,
                )
                intervals[record.timestamp] = {
                    "usage": record.usage,
                    "import": import_kwh,
                    "export": export_kwh,
                    "cost": record.cost,
                    "isEstimated": record.is_estimated,
                }
                changed = True
                continue

            old_import = _safe_float(existing.get("import")) or 0.0
            old_export = _safe_float(existing.get("export")) or 0.0
            import_diff = max(import_kwh - old_import, 0.0)
            export_diff = max(export_kwh - old_export, 0.0)

            if import_diff > 0:
                self._data["total_import_kwh"] = round(
                    float(self._data.get("total_import_kwh", 0.0)) + import_diff,
                    6,
                )
                changed = True
            if export_diff > 0:
                self._data["total_export_kwh"] = round(
                    float(self._data.get("total_export_kwh", 0.0)) + export_diff,
                    6,
                )
                changed = True

            if existing.get("usage") != record.usage or existing.get("isEstimated") != record.is_estimated:
                existing.update(
                    {
                        "usage": record.usage,
                        "import": max(old_import, import_kwh),
                        "export": max(old_export, export_kwh),
                        "cost": record.cost,
                        "isEstimated": record.is_estimated,
                    }
                )
                changed = True

        changed = self._prune_intervals(intervals) or changed

        if changed:
            await self._store.async_save(self._data)

        return {
            "total_import_kwh": round(float(self._data.get("total_import_kwh", 0.0)), 3),
            "total_export_kwh": round(float(self._data.get("total_export_kwh", 0.0)), 3),
            "tracked_interval_count": len(intervals),
        }

    def _prune_intervals(self, intervals: dict[str, Any]) -> bool:
        cutoff = _utcnow() - timedelta(days=370)
        to_delete: list[str] = []
        for timestamp in intervals:
            try:
                if _parse_iso_z(timestamp) < cutoff:
                    to_delete.append(timestamp)
            except ValueError:
                to_delete.append(timestamp)

        for timestamp in to_delete:
            intervals.pop(timestamp, None)

        return bool(to_delete)


class EntergyDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for Entergy usage polling."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: EntergyApiClient,
        account_id: str,
        entry_id: str,
        scan_interval_seconds: int = DEFAULT_SCAN_INTERVAL_SECONDS,
    ) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_{account_id}",
            update_interval=timedelta(seconds=scan_interval_seconds),
        )
        self._client = client
        self._account_id = account_id
        self._usage_store = EntergyUsageStore(hass, entry_id)

    async def async_initialize(self) -> None:
        """Load persistent state."""
        await self._usage_store.async_load()

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            payload = await self._client.async_fetch_current_usage(self._account_id)
            parsed = parse_usage_payload(payload)
            if not parsed:
                raise UpdateFailed("Unexpected weeklyusage payload")

            totals = await self._usage_store.async_process(parsed.pop("hourly_records", []))
            parsed.update(totals)
            parsed["last_update"] = _utcnow().isoformat()
            return parsed

        except (EntergyAuthError, EntergyApiError) as err:
            raise UpdateFailed(str(err)) from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Unexpected error: {err}") from err
