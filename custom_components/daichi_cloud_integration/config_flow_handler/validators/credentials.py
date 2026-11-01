"""
Credential validators.

Validation functions for user credentials and authentication.

When this file grows, consider splitting into:
- credentials.py: Basic credential validation
- oauth.py: OAuth-specific validation
- api_auth.py: API authentication methods
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.daichi_cloud_integration.api import DaichiCloudClimateApiClient
from custom_components.daichi_cloud_integration.api.client import (
    DaichiCloudClimateApiClientAuthenticationError,
    DaichiCloudClimateApiClientCommunicationError,
)
from homeassistant.helpers.aiohttp_client import async_create_clientsession

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def validate_credentials(hass: HomeAssistant, username: str, password: str) -> dict[str, str]:
    """
    Validate user credentials by testing API connection.

    Args:
        hass: Home Assistant instance.
        username: The username to validate.
        password: The password to validate.

    Raises:
        DaichiCloudClimateApiClientAuthenticationError: If credentials are invalid.
        DaichiCloudClimateApiClientCommunicationError: If communication fails.
        DaichiCloudClimateApiClientError: For other API errors.

    """
    client = DaichiCloudClimateApiClient(
        username=username,
        password=password,
        session=async_create_clientsession(hass),
    )
    """await client.async_get_data()  """

    try:
        await client.async_authenticate()
        await client.async_get_devices()
    except DaichiCloudClimateApiClientAuthenticationError:
        raise
    except Exception as err:
        raise DaichiCloudClimateApiClientCommunicationError from err

    return {"title": f"Daichi ({username})"}


__all__ = [
    "validate_credentials",
]
