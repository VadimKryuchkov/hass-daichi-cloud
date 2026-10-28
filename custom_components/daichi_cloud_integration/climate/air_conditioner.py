"""Air conditioner climate entity for daichi_cloud_integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.daichi_cloud_integration.entity import DaichiCloudClimateEntity
from homeassistant.components.climate import ClimateEntity, ClimateEntityDescription
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.const import UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError

if TYPE_CHECKING:
    from custom_components.daichi_cloud_integration.coordinator import DaichiCloudClimateDataUpdateCoordinator

ENTITY_DESCRIPTION = ClimateEntityDescription(
    key="air_conditioner",
    translation_key="air_conditioner",
    icon="mdi:air-conditioner",
    has_entity_name=True,
)


class DaichiCloudClimateAirConditioner(ClimateEntity, DaichiCloudClimateEntity):
    """Climate entity scaffold for a Daichi Cloud air conditioner."""

    entity_description = ENTITY_DESCRIPTION
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
    ]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: DaichiCloudClimateDataUpdateCoordinator) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator, ENTITY_DESCRIPTION)

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode from coordinator data."""
        value = self.coordinator.data.get("hvac_mode")
        if not isinstance(value, str):
            return None

        try:
            return HVACMode(value)
        except ValueError:
            return None

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature from coordinator data."""
        return self._get_temperature("current_temperature")

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature from coordinator data."""
        return self._get_temperature("target_temperature")

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode once Daichi Cloud API support is implemented."""
        raise HomeAssistantError("Climate control is not implemented yet.")

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature once Daichi Cloud API support is implemented."""
        raise HomeAssistantError("Climate control is not implemented yet.")

    def _get_temperature(self, key: str) -> float | None:
        """Return a numeric temperature value from coordinator data."""
        value = self.coordinator.data.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return float(value)
