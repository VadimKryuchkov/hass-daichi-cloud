"""Air conditioner climate entity for daichi_cloud_integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.daichi_cloud_integration.entity import DaichiCloudClimateEntity
from homeassistant.components.climate import ClimateEntity, ClimateEntityDescription
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError

if TYPE_CHECKING:
    from custom_components.daichi_cloud_integration.coordinator import DaichiCloudClimateDataUpdateCoordinator

HVAC_MODE_TO_ACTION = {
    HVACMode.AUTO: "mode_auto",
    HVACMode.COOL: "mode_cool",
    HVACMode.HEAT: "mode_heat",
    HVACMode.DRY: "mode_dry",
    HVACMode.FAN_ONLY: "mode_fan",
}

ENTITY_DESCRIPTION = ClimateEntityDescription(
    key="air_conditioner",
    translation_key="air_conditioner",
    icon="mdi:air-conditioner",
    has_entity_name=True,
)


class DaichiCloudClimateAirConditioner(ClimateEntity, DaichiCloudClimateEntity):
    """Climate entity for a Daichi Cloud air conditioner."""

    entity_description = ENTITY_DESCRIPTION
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0

    def __init__(self, coordinator: DaichiCloudClimateDataUpdateCoordinator) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator, ENTITY_DESCRIPTION)
        self._attr_min_temp = self._get_temperature_limit("min_temp", 16.0)
        self._attr_max_temp = self._get_temperature_limit("max_temp", 30.0)

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return HVAC modes that have control functions on this device."""
        function_ids = self._function_ids
        modes = [HVACMode.OFF] if "power" in function_ids else []
        modes.extend(mode for mode, action in HVAC_MODE_TO_ACTION.items() if action in function_ids)
        return modes

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return climate features available on this device."""
        if "temperature" in self._function_ids:
            return ClimateEntityFeature.TARGET_TEMPERATURE
        return ClimateEntityFeature(0)

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
        """Set the HVAC mode through the coordinator."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_control_function("power", False)
            return

        action = HVAC_MODE_TO_ACTION.get(hvac_mode)
        if action is None:
            raise HomeAssistantError(f"Unsupported HVAC mode: {hvac_mode}")
        await self.coordinator.async_control_function(action, True)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature through the coordinator."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
            raise HomeAssistantError("A numeric target temperature is required.")
        if not self.min_temp <= temperature <= self.max_temp:
            raise HomeAssistantError(f"Target temperature must be between {self.min_temp:g} and {self.max_temp:g} °C.")
        await self.coordinator.async_control_function("temperature", temperature)

    @property
    def _function_ids(self) -> dict[str, int]:
        """Return function IDs discovered from the current device state."""
        function_ids = self.coordinator.data.get("function_ids")
        if not isinstance(function_ids, dict):
            return {}
        return {
            key: value
            for key, value in function_ids.items()
            if isinstance(key, str) and isinstance(value, int) and not isinstance(value, bool)
        }

    def _get_temperature_limit(self, key: str, default: float) -> float:
        """Return a valid temperature limit from the device metadata."""
        value = self.coordinator.data.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return default
        return float(value)

    def _get_temperature(self, key: str) -> float | None:
        """Return a numeric temperature value from coordinator data."""
        value = self.coordinator.data.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return float(value)
