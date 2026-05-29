"""Constants for the Entergy integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "entergy_mobile"

CONF_ACCOUNT_ID: Final = "account_id"
CONF_LANGUAGE: Final = "language"
CONF_SCAN_INTERVAL_SECONDS: Final = "scan_interval_seconds"

DEFAULT_LANGUAGE: Final = "en"
DEFAULT_APP_VERSION: Final = "3.59.0"
DEFAULT_SCAN_INTERVAL_SECONDS: Final = 3600
MIN_SCAN_INTERVAL_SECONDS: Final = 60
MAX_SCAN_INTERVAL_SECONDS: Final = 86400

BASE_URL: Final = "https://prod.entergy.mindgrb.io/api"
APP_CONFIG_URL: Final = f"{BASE_URL}/app"
LOGIN_URL: Final = f"{BASE_URL}/login"
LOGOUT_URL: Final = f"{BASE_URL}/logout"
ACCOUNTS_URL: Final = f"{BASE_URL}/accounts"
WEEKLY_USAGE_URL: Final = f"{BASE_URL}/accounts/{{account_id}}/weeklyusage"

STORAGE_VERSION: Final = 1
STORAGE_KEY_PREFIX: Final = "entergy_mobile_usage"

ATTR_ACCOUNT_ID: Final = "account_id"
ATTR_LAST_UPDATE: Final = "last_update"
ATTR_LAST_INTERVAL: Final = "last_interval"
ATTR_IS_ESTIMATED: Final = "is_estimated"
