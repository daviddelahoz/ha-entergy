"""Config flow for Entergy."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EntergyApiClient, EntergyApiError, EntergyAuthError, EntergyMfaRequired
from .const import (
    CONF_ACCOUNT_ID,
    CONF_LANGUAGE,
    CONF_SCAN_INTERVAL_SECONDS,
    DEFAULT_LANGUAGE,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    MAX_SCAN_INTERVAL_SECONDS,
    MIN_SCAN_INTERVAL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


def _user_schema(default_language: str = DEFAULT_LANGUAGE) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_LANGUAGE, default=default_language): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": "en", "label": "English"},
                        {"value": "es", "label": "Spanish"},
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


def _extract_accounts(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]

    if isinstance(raw, dict):
        for key in ("accounts", "data", "items", "results"):
            value = raw.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]

        accounts = []
        for value in raw.values():
            if isinstance(value, dict):
                accounts.append(value)
        if accounts:
            return accounts

    return []


def _account_id(account: dict[str, Any]) -> str | None:
    for key in (
        "id",
        "accountId",
        "accountID",
        "account_id",
        "accountNumber",
        "account_number",
        "number",
    ):
        value = account.get(key)
        if value:
            return str(value)
    return None


def _account_label(account: dict[str, Any]) -> str:
    account_id = _account_id(account) or "Unknown"
    for key in ("nickname", "name", "serviceAddress", "address", "premiseAddress"):
        value = account.get(key)
        if value:
            return f"{account_id} - {value}"
    return account_id


async def _validate_and_fetch_accounts(
    hass: HomeAssistant,
    username: str,
    password: str,
    language: str,
) -> list[dict[str, Any]]:
    session = async_get_clientsession(hass)
    client = EntergyApiClient(
        session=session,
        username=username,
        password=password,
        language=language,
    )
    await client.async_initialize()
    await client.async_login()
    raw = await client.async_get_accounts()
    return _extract_accounts(raw)


class EntergyMobileConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an Entergy config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._flow_data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle username/password step."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=_user_schema(), errors=errors)

        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]
        language = user_input.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)

        try:
            accounts = await _validate_and_fetch_accounts(self.hass, username, password, language)
        except EntergyMfaRequired as err:
            _LOGGER.debug("Entergy setup requires unsupported MFA step: %s", err)
            errors["base"] = "mfa_required"
            return self.async_show_form(step_id="user", data_schema=_user_schema(language), errors=errors)
        except EntergyAuthError as err:
            _LOGGER.debug("Entergy setup authentication failed: %s", err)
            errors["base"] = "invalid_auth"
            return self.async_show_form(step_id="user", data_schema=_user_schema(language), errors=errors)
        except (EntergyApiError, ClientError) as err:
            _LOGGER.debug("Entergy setup connection/API failed: %s", err)
            errors["base"] = "cannot_connect"
            return self.async_show_form(step_id="user", data_schema=_user_schema(language), errors=errors)
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Unexpected Entergy setup error: %s", err)
            errors["base"] = "unknown"
            return self.async_show_form(step_id="user", data_schema=_user_schema(language), errors=errors)

        account_options = []
        for account in accounts:
            account_identifier = _account_id(account)
            if account_identifier:
                account_options.append({"value": account_identifier, "label": _account_label(account)})

        if not account_options:
            errors["base"] = "no_accounts"
            return self.async_show_form(step_id="user", data_schema=_user_schema(language), errors=errors)

        self._flow_data = {
            CONF_USERNAME: username,
            CONF_PASSWORD: password,
            CONF_LANGUAGE: language,
            "account_options": account_options,
        }
        return await self.async_step_account()

    async def async_step_account(self, user_input: dict[str, Any] | None = None):
        """Handle account selection."""
        if not self._flow_data:
            return await self.async_step_user()

        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="account",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_ACCOUNT_ID): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=self._flow_data["account_options"],
                                mode=selector.SelectSelectorMode.DROPDOWN,
                            )
                        )
                    }
                ),
                errors=errors,
            )

        account_id = user_input[CONF_ACCOUNT_ID]
        username = self._flow_data[CONF_USERNAME]

        await self.async_set_unique_id(f"{username}_{account_id}")
        self._abort_if_unique_id_configured()

        data = {
            CONF_USERNAME: username,
            CONF_PASSWORD: self._flow_data[CONF_PASSWORD],
            CONF_LANGUAGE: self._flow_data[CONF_LANGUAGE],
            CONF_ACCOUNT_ID: account_id,
        }

        return self.async_create_entry(
            title=f"Entergy {account_id}",
            data=data,
            options={CONF_SCAN_INTERVAL_SECONDS: DEFAULT_SCAN_INTERVAL_SECONDS},
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Return options flow."""
        return EntergyMobileOptionsFlow(config_entry)


class EntergyMobileOptionsFlow(config_entries.OptionsFlow):
    """Options flow for Entergy."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL_SECONDS,
                        default=self._config_entry.options.get(
                            CONF_SCAN_INTERVAL_SECONDS,
                            DEFAULT_SCAN_INTERVAL_SECONDS,
                        ),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(
                            min=MIN_SCAN_INTERVAL_SECONDS,
                            max=MAX_SCAN_INTERVAL_SECONDS,
                        ),
                    ),
                }
            ),
        )
