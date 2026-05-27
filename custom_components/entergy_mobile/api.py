"""API client for Entergy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import logging
from typing import Any

import aiohttp

from .const import (
    ACCOUNTS_URL,
    APP_CONFIG_URL,
    BASE_URL,
    DEFAULT_APP_VERSION,
    DEFAULT_LANGUAGE,
    LOGIN_URL,
    LOGOUT_URL,
    WEEKLY_USAGE_URL,
)

_LOGGER = logging.getLogger(__name__)


class EntergyApiError(Exception):
    """Base Entergy API error."""


class EntergyAuthError(EntergyApiError):
    """Authentication failed or expired."""


class EntergyMfaRequired(EntergyAuthError):
    """The API requested another authentication action that is not supported."""


@dataclass
class EntergyLoginResult:
    """Login result."""

    access_token: str
    raw: dict[str, Any]


class EntergyApiClient:
    """Small async client for prod.entergy.mindgrb.io."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        app_version: str = DEFAULT_APP_VERSION,
        language: str = DEFAULT_LANGUAGE,
        timeout_seconds: int = 30,
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._app_version = app_version
        self._language = language
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._client_id: str | None = None
        self._access_token: str | None = None

    @property
    def client_id(self) -> str | None:
        """Return the current client ID."""
        return self._client_id

    @property
    def access_token(self) -> str | None:
        """Return the current access token."""
        return self._access_token

    async def async_initialize(self) -> None:
        """Initialize client metadata required by the Entergy API."""
        self._client_id = await self.async_get_client_id()

    async def async_get_client_id(self) -> str:
        """Fetch clientId from /api/app."""
        _LOGGER.debug("Fetching Entergy app config")
        async with self._session.get(APP_CONFIG_URL, timeout=self._timeout) as resp:
            body = await self._read_body(resp)
            if resp.status >= 400:
                raise EntergyApiError(f"Could not fetch app config: HTTP {resp.status}")
            if not isinstance(body, dict):
                raise EntergyApiError("Unexpected app config response")

        client_id = body.get("clientId")
        if not client_id:
            data = body.get("data")
            if isinstance(data, dict):
                client_id = data.get("clientId")
        if not client_id:
            raise EntergyApiError("clientId missing from /api/app response")
        _LOGGER.debug("Fetched Entergy app config with clientId present")
        return str(client_id)

    def _params(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {
            "appVersion": self._app_version,
            "language": self._language,
        }
        if extra:
            params.update(extra)
        return params

    def _headers(self, token: str | None = None) -> dict[str, str]:
        if not self._client_id:
            raise EntergyApiError("Client not initialized")
        bearer = token if token is not None else self._access_token
        if not bearer:
            bearer = "0"
        return {
            "Accept": "application/json",
            "clientId": self._client_id,
            "Authorization": f"Bearer {bearer}",
        }

    async def _read_body(self, resp: aiohttp.ClientResponse) -> Any:
        content_type = resp.headers.get("content-type", "")
        if "json" in content_type:
            return await resp.json(content_type=None)
        text = await resp.text()
        try:
            return await resp.json(content_type=None)
        except Exception:
            return text

    async def async_login(self) -> EntergyLoginResult:
        """Login and store the returned access token."""
        if not self._client_id:
            await self.async_initialize()

        payload = {"username": self._username, "password": self._password}
        _LOGGER.debug("Logging in to Entergy API")

        async with self._session.post(
            LOGIN_URL,
            params=self._params(),
            headers={**self._headers("0"), "Content-Type": "application/json"},
            json=payload,
            timeout=self._timeout,
        ) as resp:
            body = await self._read_body(resp)
            status = resp.status

        if status in (401, 403):
            raise EntergyAuthError(f"Login failed: HTTP {status}")
        if status >= 400:
            raise EntergyApiError(f"Login failed: HTTP {status}: {str(body)[:300]}")
        if not isinstance(body, dict):
            raise EntergyApiError("Unexpected login response")

        login_data = body.get("data")
        if not isinstance(login_data, dict):
            login_data = body

        next_action = login_data.get("nextAction") or body.get("nextAction")
        if next_action:
            raise EntergyMfaRequired(f"Login requires unsupported nextAction: {next_action}")

        token = (
            login_data.get("accessToken")
            or login_data.get("access_token")
            or login_data.get("token")
            or body.get("accessToken")
            or body.get("access_token")
            or body.get("token")
        )
        if not token:
            raise EntergyAuthError("Login response did not contain an access token")

        self._access_token = str(token)
        _LOGGER.debug("Entergy API login succeeded")
        return EntergyLoginResult(access_token=self._access_token, raw=body)

    async def async_logout(self) -> None:
        """Logout best-effort."""
        if not self._client_id:
            return
        try:
            async with self._session.post(
                LOGOUT_URL,
                params=self._params(),
                headers=self._headers(),
                timeout=self._timeout,
            ):
                pass
        except Exception as err:
            _LOGGER.debug("Logout failed: %s", err)

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        retry_auth: bool = True,
    ) -> Any:
        if not self._client_id:
            await self.async_initialize()
        if not self._access_token:
            await self.async_login()

        _LOGGER.debug("Requesting Entergy API: %s %s", method, url)
        async with self._session.request(
            method,
            url,
            params=self._params(params),
            headers=self._headers(),
            timeout=self._timeout,
        ) as resp:
            body = await self._read_body(resp)
            status = resp.status

        if status == 401 and retry_auth:
            _LOGGER.debug("Entergy API returned 401; refreshing login and retrying")
            await self.async_login()
            return await self._request_json(method, url, params=params, retry_auth=False)

        if status in (401, 403):
            raise EntergyAuthError(f"Unauthorized: HTTP {status}")
        if status >= 400:
            raise EntergyApiError(f"API request failed: HTTP {status}: {str(body)[:300]}")
        return body

    async def async_get_accounts(self) -> Any:
        """Fetch the user's accounts."""
        return await self._request_json("GET", ACCOUNTS_URL)

    async def async_get_account(self, account_id: str) -> Any:
        """Fetch one account."""
        return await self._request_json("GET", f"{ACCOUNTS_URL}/{account_id}")

    async def async_get_weekly_usage(
        self,
        account_id: str,
        start_date: date,
        view: str = "day",
    ) -> Any:
        """Fetch weekly usage payload for an account."""
        url = WEEKLY_USAGE_URL.format(account_id=account_id)
        return await self._request_json(
            "GET",
            url,
            params={"view": view, "startDate": start_date.isoformat()},
        )

    async def async_fetch_current_usage(self, account_id: str) -> Any:
        """Fetch the latest usage window."""
        today = date.today()
        return await self.async_get_weekly_usage(
            account_id=account_id,
            start_date=today - timedelta(days=6),
            view="day",
        )

    def absolute_url(self, path: str) -> str:
        """Return an absolute API URL for diagnostics/tests."""
        path = path.lstrip("/")
        return f"{BASE_URL}/{path}"
