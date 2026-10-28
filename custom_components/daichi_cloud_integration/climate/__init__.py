"""Climate platform for daichi_cloud_integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.daichi_cloud_integration.const import PARALLEL_UPDATES as PARALLEL_UPDATES

from .air_conditioner import DaichiCloudClimateAirConditioner

if TYPE_CHECKING:
    from custom_components.daichi_cloud_integration.data import DaichiCloudClimateConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaichiCloudClimateConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the climate platform."""
    async_add_entities(
        [DaichiCloudClimateAirConditioner(entry.runtime_data.coordinator)],
    )
