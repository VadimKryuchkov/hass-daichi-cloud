"""Set up the Daichi Cloud integration."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.loader import async_get_loaded_integration

from .api import DaichiCloudClimateApiClient
from .const import CONF_DEVICE_ID, DEFAULT_UPDATE_INTERVAL_HOURS, DOMAIN, LOGGER
from .coordinator import DaichiCloudClimateDataUpdateCoordinator
from .data import DaichiCloudClimateData
from .service_actions import async_setup_services

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import DaichiCloudClimateConfigEntry

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.FAN,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up integration-level services."""
    await async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaichiCloudClimateConfigEntry,
) -> bool:
    """Set up a Daichi Cloud config entry."""
    device_id = entry.data.get(CONF_DEVICE_ID)
    if isinstance(device_id, bool) or not isinstance(device_id, int) or device_id <= 0:
        raise ConfigEntryError(
            "This entry predates device selection. Remove it and add the integration again for each device."
        )

    client = DaichiCloudClimateApiClient(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
    )
    coordinator = DaichiCloudClimateDataUpdateCoordinator(
        hass=hass,
        logger=LOGGER,
        name=DOMAIN,
        config_entry=entry,
        update_interval=timedelta(
            hours=entry.options.get("update_interval_hours", DEFAULT_UPDATE_INTERVAL_HOURS),
        ),
        always_update=False,
    )

    entry.runtime_data = DaichiCloudClimateData(
        client=client,
        coordinator=coordinator,
        integration=async_get_loaded_integration(hass, entry.domain),
    )

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: DaichiCloudClimateConfigEntry,
) -> bool:
    """Unload the platforms for a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: DaichiCloudClimateConfigEntry,
) -> None:
    """Reload a config entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
