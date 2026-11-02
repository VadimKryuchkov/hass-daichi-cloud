"""Client for the unofficial Daichi Comfort Cloud API."""

from __future__ import annotations

import asyncio
import json
import secrets
from typing import Any

import aiohttp

from custom_components.daichi_cloud_integration.const import DEFAULT_API_URL, DEFAULT_CLIENT_ID, LOGGER


class DaichiCloudClimateApiClientError(Exception):
    """Base exception for API errors."""


class DaichiCloudClimateApiClientCommunicationError(DaichiCloudClimateApiClientError):
    """Exception raised for network, HTTP, or response errors."""


class DaichiCloudClimateApiClientAuthenticationError(DaichiCloudClimateApiClientError):
    """Exception raised when authentication fails."""


REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


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
        self._buildings: list[dict[str, Any]] | None = None
        self._devices: list[dict[str, Any]] | None = None

    async def async_authenticate(self) -> None:
        """Authenticate and store the API access token."""
        # @todo Добавить проверку валидности email
        """await self._async_request_json(
            "POST",
            "/user/credentials",
            payload={"email": self._username},
            authenticated=False,
            expect_json=False,
            expected_statuses=(200, 201),
        )"""

        payload = {
            "grant_type": "password",
            "email": self._username,
            "password": self._password,
            "clientId": DEFAULT_CLIENT_ID,
        }

        async with self._session.post(
            f"{self._base_url}/token",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        ) as token_response:
            if token_response.status in (401, 403):
                msg = "Daichi Cloud rejected the credentials or access token"
                raise DaichiCloudClimateApiClientAuthenticationError(msg)
            if token_response.status != 200:
                error_text = await token_response.text()
                LOGGER.error(
                    "Token request failed: %s - %s",
                    token_response.status,
                    error_text,
                )
                raise DaichiCloudClimateApiClientCommunicationError(
                    f"Authentication request failed with HTTP {token_response.status}"
                )

            try:
                token_data = await token_response.json()
            except (aiohttp.ContentTypeError, json.JSONDecodeError) as exception:
                msg = "Daichi Cloud returned an invalid authentication response"
                raise DaichiCloudClimateApiClientCommunicationError(msg) from exception

        token = self._extract_access_token(token_data)
        LOGGER.debug("Daichi Cloud authentication succeeded")

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

    async def async_get_devices(
        self,
        building_id: int | None = None,
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        """Return the list of devices, optionally filtered by building ID."""
        if self._devices is not None and not force_refresh and building_id is None:
            return self._devices

        def get_building_devices(building: dict[str, Any]) -> list[dict[str, Any]]:
            places = building.get("places", [])
            if not isinstance(places, list) or not all(isinstance(device, dict) for device in places):
                msg = "Daichi Cloud returned invalid device data"
                raise DaichiCloudClimateApiClientCommunicationError(msg)
            return places

        try:
            buildings = await self.async_get_buildings(force_refresh=force_refresh)
            all_devices: list[dict[str, Any]] = []
            for building in buildings:
                if building_id is not None and building.get("id") != building_id:
                    continue
                places = get_building_devices(building)
                all_devices.extend(places)
                LOGGER.debug(
                    "Found %d devices in building '%s'",
                    len(places),
                    building.get("title", "Unknown"),
                )

            if building_id is None:
                self._devices = all_devices
            LOGGER.debug("Fetched %d devices total", len(all_devices))
        except DaichiCloudClimateApiClientError:
            raise
        except Exception as err:
            LOGGER.error("Failed to fetch devices: %s", err)
            raise DaichiCloudClimateApiClientCommunicationError(f"Failed to fetch devices: {err}") from err
        return all_devices

    async def async_get_buildings(self, force_refresh: bool = False) -> list[dict[str, Any]]:
        """Return buildings, using the local cache unless a refresh is requested."""
        if self._buildings is not None and not force_refresh:
            return self._buildings

        def validate_buildings_response(
            response: dict[str, Any] | list[Any] | None,
        ) -> list[dict[str, Any]]:
            if isinstance(response, list):
                buildings = response
            elif isinstance(response, dict) and isinstance(response.get("data"), list):
                buildings = response["data"]
            else:
                msg = "Daichi Cloud returned an unexpected buildings response"
                raise DaichiCloudClimateApiClientCommunicationError(msg)

            if not all(isinstance(building, dict) for building in buildings):
                msg = "Daichi Cloud returned invalid building data"
                raise DaichiCloudClimateApiClientCommunicationError(msg)
            return buildings

        try:
            response = await self._async_request_json("GET", "/buildings")
            self._buildings = validate_buildings_response(response)

            LOGGER.debug("Fetched %d buildings", len(self._buildings or []))
        except DaichiCloudClimateApiClientError:
            raise
        except Exception as err:
            LOGGER.error("Failed to fetch buildings: %s", err)
            raise DaichiCloudClimateApiClientCommunicationError(f"Failed to fetch buildings: {err}") from err
        return self._buildings or []

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
        value: float | bool | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a function command to a device."""
        if device_id <= 0:
            msg = "Device ID must be a positive integer"
            raise ValueError(msg)
        if isinstance(function_id, bool) or function_id <= 0:
            msg = "Function ID must be a positive integer"
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
        if response.get("done") is False:
            details = self._extract_error_details(response)
            msg = f"Daichi Cloud rejected the device control command: {details or 'command was not completed'}"
            raise DaichiCloudClimateApiClientCommunicationError(msg)
        if response.get("errors"):
            details = self._extract_error_details(response)
            msg = f"Daichi Cloud rejected the device control command: {details or 'unknown API error'}"
            raise DaichiCloudClimateApiClientCommunicationError(msg)
        return response

    # @todo Add retry logic
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
            try:
                await self.async_authenticate()
            except TimeoutError as exception:
                msg = "Timed out while authenticating with Daichi Cloud"
                raise DaichiCloudClimateApiClientCommunicationError(msg) from exception
            except aiohttp.ClientError as exception:
                msg = "Unable to authenticate with Daichi Cloud"
                raise DaichiCloudClimateApiClientCommunicationError(msg) from exception

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Home Assistant Integration",
        }
        if authenticated and self._access_token is not None:
            headers["Authorization"] = f"Bearer {self._access_token}"

        try:
            LOGGER.debug(
                "Daichi Cloud request: method=%s path=%s params=%s payload=%s",
                method,
                path,
                params,
                self._redact_request_data(payload),
            )
            async with asyncio.timeout(REQUEST_TIMEOUT.total):
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
                        error_text = await response.text()
                        try:
                            error_data = json.loads(error_text)
                        except json.JSONDecodeError:
                            error_data = None
                        details = self._extract_error_details(error_data)
                        msg = f"Daichi Cloud request failed with HTTP {response.status}"
                        if details:
                            msg = f"{msg}: {details}"
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

    @staticmethod
    def _extract_error_details(response: Any) -> str | None:
        """Return useful error details from a Daichi API response."""
        if not isinstance(response, dict):
            return None

        message = response.get("message")
        details: list[str] = [message.strip()] if isinstance(message, str) and message.strip() else []

        errors = response.get("errors")
        if isinstance(errors, dict):
            for field, error in errors.items():
                if isinstance(error, str):
                    error_text = error
                elif isinstance(error, list):
                    error_text = ", ".join(str(item) for item in error)
                else:
                    error_text = str(error)
                if error_text:
                    details.append(f"{field}: {error_text}")
        elif isinstance(errors, list):
            details.extend(str(error) for error in errors if error)
        elif isinstance(errors, str) and errors:
            details.append(errors)

        unique_details = list(dict.fromkeys(details))
        return "; ".join(unique_details) or None

    @classmethod
    def _redact_request_data(cls, data: Any) -> Any:
        """Redact sensitive fields before request parameters are written to logs."""
        sensitive_fields = ("password", "token", "authorization", "email", "username", "secret")
        if isinstance(data, dict):
            return {
                key: (
                    "REDACTED"
                    if any(field in str(key).casefold() for field in sensitive_fields)
                    else cls._redact_request_data(value)
                )
                for key, value in data.items()
            }
        if isinstance(data, list):
            return [cls._redact_request_data(value) for value in data]
        return data
