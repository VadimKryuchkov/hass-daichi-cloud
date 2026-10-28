"""Sensor platform for daichi_cloud_integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.daichi_cloud_integration.const import PARALLEL_UPDATES as PARALLEL_UPDATES
from homeassistant.components.sensor import SensorEntityDescription

from .diagnostic import ENTITY_DESCRIPTIONS as DIAGNOSTIC_DESCRIPTIONS, DaichiCloudClimateDiagnosticSensor

if TYPE_CHECKING:
    from custom_components.daichi_cloud_integration.data import DaichiCloudClimateConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

ENTITY_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = DIAGNOSTIC_DESCRIPTIONS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaichiCloudClimateConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    async_add_entities(
        DaichiCloudClimateDiagnosticSensor(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
        )
        for entity_description in DIAGNOSTIC_DESCRIPTIONS
    )
