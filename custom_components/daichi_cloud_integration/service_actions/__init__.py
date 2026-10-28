"""Service actions package for daichi_cloud_integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.daichi_cloud_integration.const import DOMAIN, LOGGER
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from custom_components.daichi_cloud_integration.data import DaichiCloudClimateConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse

SERVICE_RELOAD_DATA = "reload_data"


async def async_setup_services(hass: HomeAssistant) -> None:
    """
    Register services for the integration.

    Services are registered at component level (in async_setup) rather than
    per config entry. This is a Silver Quality Scale requirement and ensures:
    - Service validation works correctly
    - Services are available even without config entries
    - Helpful error messages are provided

    Service handlers iterate over all config entries to find the relevant one.
    """

    async def handle_reload_data(call: ServiceCall) -> None:
        """Handle the reload_data service call."""
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            LOGGER.warning("No config entries found for %s", DOMAIN)
            return

        for entry in entries:
            await _async_handle_reload_data(entry)

    async def _async_handle_reload_data(entry: DaichiCloudClimateConfigEntry) -> ServiceResponse:
        """Refresh integration data and return a summary."""
        coordinator = entry.runtime_data.coordinator
        start_time = dt_util.now()

        try:
            await coordinator.async_request_refresh()
        except (UpdateFailed, ConfigEntryAuthFailed, ConfigEntryNotReady) as exception:
            LOGGER.exception("Failed to reload data: %s", exception)
            return {
                "status": "error",
                "timestamp": dt_util.now().isoformat(),
                "error": str(exception),
                "error_type": type(exception).__name__,
            }

        end_time = dt_util.now()
        duration_ms = (end_time - start_time).total_seconds() * 1000
        data_size = len(str(coordinator.data)) if coordinator.data else 0
        record_count = len(coordinator.data) if isinstance(coordinator.data, dict) else 0
        response_data: ServiceResponse = {
            "status": "success",
            "timestamp": end_time.isoformat(),
            "duration_ms": round(duration_ms, 2),
            "record_count": record_count,
            "data_size_bytes": data_size,
            "last_update_success": coordinator.last_update_success,
        }

        LOGGER.info(
            "Data reload completed successfully in %.2fms with %d records",
            duration_ms,
            record_count,
        )
        return response_data

    if not hass.services.has_service(DOMAIN, SERVICE_RELOAD_DATA):
        hass.services.async_register(
            DOMAIN,
            SERVICE_RELOAD_DATA,
            handle_reload_data,
        )

    LOGGER.debug("Services registered for %s", DOMAIN)
