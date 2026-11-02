"""
Data processing utilities for the coordinator.

This module provides functions for processing, transforming, and validating
data received from the API before distributing it to entities.

Use cases:
- Data normalization and validation
- Caching strategies for expensive computations
- Data transformation for entity consumption
- Aggregation of multiple API responses
"""

from __future__ import annotations

import re
from typing import Any

from custom_components.daichi_cloud_integration.api.const import (
    FUNCTION_ID_AUTO,
    FUNCTION_ID_COOL,
    FUNCTION_ID_DRY,
    FUNCTION_ID_FAN,
    FUNCTION_ID_HEAT,
    FUNCTION_ID_POWER,
    FUNCTION_ID_TEMPERATURE,
)
from custom_components.daichi_cloud_integration.const import LOGGER

FUNCTION_ID_TO_ACTION = {
    FUNCTION_ID_POWER: "power",
    FUNCTION_ID_TEMPERATURE: "temperature",
    FUNCTION_ID_COOL: "mode_cool",
    FUNCTION_ID_HEAT: "mode_heat",
    FUNCTION_ID_AUTO: "mode_auto",
    FUNCTION_ID_DRY: "mode_dry",
    FUNCTION_ID_FAN: "mode_fan",
}

ACTION_ALIASES = {
    "power": ("power", "onoff", "poweronoff", "питание", "включение", "выключение"),
    "temperature": ("temperature", "settemp", "targettemperature", "температура", "уставка"),
    "mode_cool": ("cool", "cooling", "modecool", "coolingmode", "охлаждение", "охлаждения"),
    "mode_heat": ("heat", "heating", "modeheat", "heatingmode", "обогрев", "нагрев"),
    "mode_auto": ("auto", "automatic", "modeauto", "automode", "авто", "автоматический"),
    "mode_dry": ("dry", "dehumidification", "modedry", "drymode", "осушение", "осушения"),
    "mode_fan": ("fan", "fanonly", "modefan", "fanmode", "vent", "ventilation", "вентиляция", "обдув"),
}

FUNCTION_METADATA_FIELDS = (
    "name",
    "title",
    "key",
    "code",
    "tag",
    "bleTag",
    "bleCommand",
    "command",
    "functionName",
    "mode",
)

ICON_TO_HVAC_MODE = {
    "modeCool_active": "cool",
    "modeHeat_active": "heat",
    "modeAuto_active": "auto",
    "modeDry_active": "dry",
    "modeFan_active": "fan_only",
}


def validate_api_response(data: Any) -> bool:
    """
    Validate the structure and content of API response data.

    Args:
        data: The raw data received from the API.

    Returns:
        True if the data is valid, False otherwise.

    Example:
        >>> data = {"userId": 1, "id": 1, "title": "Test"}
        >>> validate_api_response(data)
        True
    """
    if not isinstance(data, dict):
        LOGGER.warning("Invalid API response: expected dict, got %s", type(data).__name__)
        return False

    # Add validation logic based on your API structure
    # This is a placeholder for future implementation
    return True


def transform_api_data(raw_data: Any) -> dict[str, Any]:
    """
    Transform raw API data into a standardized format for entities.

    This function can be used to:
    - Normalize field names
    - Convert units
    - Calculate derived values
    - Restructure nested data

    Args:
        raw_data: The raw data from the API.

    Returns:
        A dictionary with transformed data ready for entity consumption.

    Example:
        >>> raw = {"temp_c": 25.5}
        >>> transform_api_data(raw)
        {"temperature": 25.5, "temperature_f": 77.9}
    """
    if not validate_api_response(raw_data):
        LOGGER.warning("Skipping transformation of invalid data")
        return raw_data if isinstance(raw_data, dict) else {}

    device_data = raw_data.get("data")
    if isinstance(device_data, dict):
        raw_data = device_data

    function_ids = _get_function_ids(raw_data)
    transformed_data = {**raw_data, "function_ids": function_ids}

    state = raw_data.get("state")
    if isinstance(state, dict):
        is_on = state.get("isOn")
        if isinstance(is_on, bool):
            transformed_data["is_on"] = is_on

        info = state.get("info")
        icon_names = info.get("iconNames") if isinstance(info, dict) else None
        if isinstance(icon_names, list):
            for icon_name in icon_names:
                if isinstance(icon_name, str) and icon_name in ICON_TO_HVAC_MODE:
                    transformed_data["hvac_mode"] = ICON_TO_HVAC_MODE[icon_name]
                    break

    if transformed_data.get("is_on") is False:
        transformed_data["hvac_mode"] = "off"
    elif "hvac_mode" not in transformed_data:
        active_modes = _get_active_hvac_modes(raw_data, function_ids)
        if len(active_modes) == 1:
            transformed_data["hvac_mode"] = active_modes[0]

    current_temperature = _get_number(raw_data.get("curTemp"))
    if current_temperature is not None:
        transformed_data["current_temperature"] = current_temperature

    temperature_function = _find_function(raw_data, function_ids.get("temperature"))
    if temperature_function is not None:
        function_state = temperature_function.get("state")
        if isinstance(function_state, dict):
            target_temperature = _get_number(function_state.get("value"))
            if target_temperature is not None:
                transformed_data["target_temperature"] = target_temperature

        for key, fields in (("min_temp", ("minValue", "min")), ("max_temp", ("maxValue", "max"))):
            for field in fields:
                value = _get_number(temperature_function.get(field))
                if value is not None:
                    transformed_data[key] = value
                    break

    return transformed_data


def _get_function_ids(device_data: dict[str, Any]) -> dict[str, int]:
    """Find control function IDs from device metadata, with known IDs as fallback."""
    pult = device_data.get("pult")
    if not isinstance(pult, list):
        return {}

    matches: dict[str, set[int]] = {}
    for section in pult:
        if not isinstance(section, dict):
            continue
        functions = section.get("functions")
        if not isinstance(functions, list):
            continue

        for function in functions:
            if not isinstance(function, dict):
                continue
            function_id = function.get("id", function.get("functionId"))
            if isinstance(function_id, bool) or not isinstance(function_id, int) or function_id <= 0:
                continue

            metadata = [function.get(field) for field in FUNCTION_METADATA_FIELDS]
            section_title = section.get("title")
            if isinstance(section_title, str):
                metadata.append(section_title)

            for action, aliases in ACTION_ALIASES.items():
                if action in ("mode_auto", "mode_fan") and any(
                    _matches_alias(value, ("fanspeed", "fan speed", "скоростьвентилятора")) for value in metadata
                ):
                    continue
                if any(_matches_alias(value, aliases) for value in metadata):
                    matches.setdefault(action, set()).add(function_id)

    function_ids = {action: next(iter(ids)) for action, ids in matches.items() if len(ids) == 1}

    function_ids.update(
        {
            action: function_id
            for function_id, action in FUNCTION_ID_TO_ACTION.items()
            if action not in matches and _find_function(device_data, function_id) is not None
        }
    )

    return function_ids


def _matches_alias(value: Any, aliases: tuple[str, ...]) -> bool:
    """Return whether a metadata value identifies a known control action."""
    if not isinstance(value, str):
        return False
    normalized = re.sub(r"[^a-zа-яё0-9]+", "", value.casefold())
    words = re.findall(r"[a-zа-яё0-9]+", value.casefold())
    return normalized in aliases or any(word in aliases for word in words)


def _find_function(device_data: dict[str, Any], function_id: int | None) -> dict[str, Any] | None:
    """Find a function in the device pult by its ID."""
    if function_id is None:
        return None
    pult = device_data.get("pult")
    if not isinstance(pult, list):
        return None
    for section in pult:
        if not isinstance(section, dict):
            continue
        functions = section.get("functions")
        if not isinstance(functions, list):
            continue
        for function in functions:
            if isinstance(function, dict) and function.get("id", function.get("functionId")) == function_id:
                return function
    return None


def _get_active_hvac_modes(device_data: dict[str, Any], function_ids: dict[str, int]) -> list[str]:
    """Return active HVAC modes based on the pult function states."""
    active_modes: list[str] = []
    for action, mode in (
        ("mode_cool", "cool"),
        ("mode_heat", "heat"),
        ("mode_auto", "auto"),
        ("mode_dry", "dry"),
        ("mode_fan", "fan_only"),
    ):
        function = _find_function(device_data, function_ids.get(action))
        function_state = function.get("state") if function else None
        if isinstance(function_state, dict) and function_state.get("isOn") is True:
            active_modes.append(mode)
    return active_modes


def _get_number(value: Any) -> float | None:
    """Convert a numeric API value to a float, rejecting booleans and invalid values."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def cache_computed_values(data: dict[str, Any]) -> dict[str, Any]:
    """
    Add computed or cached values to the coordinator data.

    This is useful for expensive calculations that should only be done once
    per update cycle rather than in each entity.

    Args:
        data: The base data dictionary.

    Returns:
        The data dictionary with additional computed values.

    Example:
        >>> data = {"power": 1000, "runtime": 3600}
        >>> cache_computed_values(data)
        {"power": 1000, "runtime": 3600, "energy_kwh": 1.0}
    """
    # Add computed values as needed
    # This is a placeholder for future implementation
    return data
