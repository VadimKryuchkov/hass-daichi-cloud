"""Client for the unofficial Daichi Comfort Cloud API."""

from __future__ import annotations

import asyncio
import json
import secrets
from typing import Any

import aiohttp

from custom_components.daichi_cloud_integration.api.const import SUPPORTED_FUNCTION_IDS
from custom_components.daichi_cloud_integration.const import DEFAULT_API_URL, DEFAULT_CLIENT_ID


class DaichiCloudClimateApiClientError(Exception):
    """Base exception for API errors."""


class DaichiCloudClimateApiClientCommunicationError(DaichiCloudClimateApiClientError):
    """Exception raised for network, HTTP, or response errors."""


class DaichiCloudClimateApiClientAuthenticationError(DaichiCloudClimateApiClientError):
    """Exception raised when authentication fails."""


class DaichiCloudClimateApiClient:
    """Communicate with Daichi Comfort Cloud."""

    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
        base_url: str = DEFAULT_API_URL,
    ) -> None:
        """Initialize the client with credentials and a Home Assistant session."""
        self._username = username
        self._password = password
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._access_token: str | None = None

    async def async_authenticate(self) -> None:
        """Authenticate and store the API access token."""
        await self._async_request_json(
            "POST",
            "/user/credentials",
            payload={"email": self._username},
            authenticated=False,
            expect_json=False,
            expected_statuses=(200, 201),
        )
        response = await self._async_request_json(
            "POST",
            "/token",
            payload={
                "email": self._username,
                "password": self._password,
                "clientId": DEFAULT_CLIENT_ID,
            },
            authenticated=False,
        )

        token = self._extract_access_token(response)
        if token is None:
            token = self._access_token
        if token is None:
            msg = "Authentication response did not contain an access token"
            raise DaichiCloudClimateApiClientCommunicationError(msg)

        token = token.removeprefix("Bearer ").strip()
        if not token:
            msg = "Authentication response contained an empty access token"
            raise DaichiCloudClimateApiClientCommunicationError(msg)
        self._access_token = token

    async def async_get_data(self) -> dict[str, Any] | list[Any]:
        """Return the raw buildings response for credential validation and refresh."""
        response = await self._async_request_json("GET", "/buildings")
        if response is None:
            msg = "Daichi Cloud returned an empty buildings response"
            raise DaichiCloudClimateApiClientCommunicationError(msg)
        return response

    async def async_get_device_state(self, device_id: int) -> dict[str, Any]:
        """Return the raw state response for one device."""
        if device_id <= 0:
            msg = "Device ID must be a positive integer"
            raise ValueError(msg)

        response = await self._async_request_json("GET", f"/devices/{device_id}")
        if not isinstance(response, dict):
            msg = "Device state response must be a JSON object"
            raise DaichiCloudClimateApiClientError(msg)
        return response

    async def async_control_device(
        self,
        device_id: int,
        function_id: int,
        value: int | bool | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a function command to a device."""
        if device_id <= 0:
            msg = "Device ID must be a positive integer"
            raise ValueError(msg)
        if function_id not in SUPPORTED_FUNCTION_IDS:
            msg = f"Unsupported Daichi Cloud function ID: {function_id}"
            raise ValueError(msg)

        command_value: dict[str, Any] = {
            "functionId": function_id,
            "parameters": parameters,
        }
        if isinstance(value, bool):
            command_value["isOn"] = value
        elif value is not None:
            command_value["value"] = value
        else:
            command_value["isOn"] = True

        response = await self._async_request_json(
            "POST",
            f"/devices/{device_id}/ctrl",
            payload={
                "cmdId": secrets.randbelow(90_000_000) + 10_000_000,
                "value": command_value,
                "conflictResolveData": None,
            },
            params={"ignoreConflicts": "false"},
        )
        if not isinstance(response, dict):
            msg = "Device control response must be a JSON object"
            raise DaichiCloudClimateApiClientError(msg)
        return response

    async def _async_request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        authenticated: bool = True,
        expect_json: bool = True,
        expected_statuses: tuple[int, ...] = (200,),
    ) -> dict[str, Any] | list[Any] | None:
        """Make a bounded HTTP request and validate its status and JSON response."""
        if authenticated and self._access_token is None:
            await self.async_authenticate()

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if authenticated and self._access_token is not None:
            headers["Authorization"] = f"Bearer {self._access_token}"

        try:
            async with asyncio.timeout(30):
                async with self._session.request(
                    method,
                    f"{self._base_url}{path}",
                    headers=headers,
                    json=payload,
                    params=params,
                ) as response:
                    if response.status in (401, 403):
                        msg = "Daichi Cloud rejected the credentials or access token"
                        raise DaichiCloudClimateApiClientAuthenticationError(msg)
                    if response.status not in expected_statuses:
                        msg = f"Daichi Cloud request failed with HTTP {response.status}"
                        raise DaichiCloudClimateApiClientCommunicationError(msg)
                    for cookie_name, cookie in response.cookies.items():
                        if path == "/token" and ("token" in cookie_name.lower() or "auth" in cookie_name.lower()):
                            self._access_token = cookie.value
                            break
                    if not expect_json:
                        return None
                    try:
                        data = await response.json()
                    except (aiohttp.ContentTypeError, json.JSONDecodeError) as exception:
                        msg = "Daichi Cloud returned an invalid JSON response"
                        raise DaichiCloudClimateApiClientCommunicationError(msg) from exception
        except TimeoutError as exception:
            msg = "Timed out while communicating with Daichi Cloud"
            raise DaichiCloudClimateApiClientCommunicationError(msg) from exception
        except aiohttp.ClientError as exception:
            msg = "Unable to communicate with Daichi Cloud"
            raise DaichiCloudClimateApiClientCommunicationError(msg) from exception

        if not isinstance(data, (dict, list)):
            msg = "Daichi Cloud returned an unexpected JSON response"
            raise DaichiCloudClimateApiClientCommunicationError(msg)
        return data

    @staticmethod
    def _extract_access_token(response: dict[str, Any] | list[Any] | None) -> str | None:
        """Extract a bearer token from known response envelope fields."""
        if not isinstance(response, dict):
            return None

        token_data = response.get("data")
        candidates = [token_data, response]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            for key in ("access_token", "token", "accessToken", "access"):
                token = candidate.get(key)
                if isinstance(token, str) and token.strip():
                    return token.strip()
        return None
