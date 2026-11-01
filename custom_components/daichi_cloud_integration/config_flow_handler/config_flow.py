"""Config flow for Daichi Cloud."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from slugify import slugify

from custom_components.daichi_cloud_integration.api import (
    DaichiCloudClimateApiClientAuthenticationError,
    DaichiCloudClimateApiClientCommunicationError,
    DaichiCloudClimateApiClientError,
)
from custom_components.daichi_cloud_integration.config_flow_handler.schemas import (
    get_device_schema,
    get_reauth_schema,
    get_reconfigure_schema,
    get_user_schema,
)
from custom_components.daichi_cloud_integration.config_flow_handler.validators import validate_credentials
from custom_components.daichi_cloud_integration.const import CONF_DEVICE_ID, DOMAIN, LOGGER
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector
from homeassistant.loader import async_get_loaded_integration

if TYPE_CHECKING:
    from custom_components.daichi_cloud_integration.config_flow_handler.options_flow import (
        DaichiCloudClimateOptionsFlow,
    )


class DaichiCloudClimateConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up and reconfigure Daichi Cloud accounts."""

    VERSION = 1
    _pending_entry_data: dict[str, Any] | None = None
    _pending_devices: list[dict[str, Any]] | None = None

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> DaichiCloudClimateOptionsFlow:
        """Return the options flow."""
        from custom_components.daichi_cloud_integration.config_flow_handler.options_flow import (  # noqa: PLC0415
            DaichiCloudClimateOptionsFlow,
        )

        return DaichiCloudClimateOptionsFlow()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle initial account setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                devices = await validate_credentials(
                    self.hass,
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                )
            except DaichiCloudClimateApiClientCommunicationError:
                errors["base"] = "connection"
            except DaichiCloudClimateApiClientAuthenticationError:
                errors["base"] = "auth"
            except DaichiCloudClimateApiClientError:
                LOGGER.exception("Daichi Cloud returned an unexpected API error during setup")
                errors["base"] = "unknown"
            except Exception:  # noqa: BLE001 - Unexpected config flow errors must be logged and shown as unknown.
                LOGGER.exception("Unexpected error in config flow")
                errors["base"] = "unknown"
            else:
                self._pending_entry_data = user_input
                self._pending_devices = devices
                if not devices:
                    errors["base"] = "no_devices"
                else:
                    return await self.async_step_device()

        integration = async_get_loaded_integration(self.hass, DOMAIN)
        assert integration.documentation is not None, "Integration documentation URL is not set in manifest.json"
        return self.async_show_form(
            step_id="user",
            data_schema=get_user_schema(user_input),
            errors=errors,
            description_placeholders={"documentation_url": integration.documentation},
        )

    async def async_step_device(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle device selection after validating account credentials."""
        if self._pending_entry_data is None or self._pending_devices is None:
            return self.async_abort(reason="device_selection_expired")

        device_options: list[selector.SelectOptionDict] = []
        devices_by_id: dict[str, dict[str, Any]] = {}
        for device in self._pending_devices:
            device_id = device.get("id")
            if isinstance(device_id, bool) or not isinstance(device_id, int) or device_id <= 0:
                continue
            device_key = str(device_id)
            title = device.get("title")
            label = title.strip() if isinstance(title, str) and title.strip() else f"Device {device_id}"
            if device_key in devices_by_id:
                continue
            devices_by_id[device_key] = device
            device_options.append({"value": device_key, "label": f"{label} (ID: {device.get('serial')})"})

        if not device_options:
            return self.async_abort(reason="no_devices")

        errors: dict[str, str] = {}
        if user_input is not None:
            selected_device = devices_by_id.get(str(user_input[CONF_DEVICE_ID]))
            if selected_device is None:
                errors["base"] = "invalid_device"
            else:
                device_id = selected_device["id"]
                username = self._pending_entry_data[CONF_USERNAME]
                await self.async_set_unique_id(f"{slugify(username).lower()}_{device_id}")
                self._abort_if_unique_id_configured()

                title = selected_device.get("title")
                device_name = title.strip() if isinstance(title, str) and title.strip() else f"Device {device_id}"
                return self.async_create_entry(
                    title=f"{device_name} ({username})",
                    data={**self._pending_entry_data, CONF_DEVICE_ID: device_id},
                )

        return self.async_show_form(
            step_id="device",
            data_schema=get_device_schema(device_options),
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle credential updates for an existing entry."""
        entry = self._get_reconfigure_entry()
        if entry.unique_id is not None:
            await self.async_set_unique_id(entry.unique_id)
            self._abort_if_unique_id_mismatch()

        errors: dict[str, str] = {}
        if user_input is not None:
            error = await self._async_validate_credentials(user_input, entry.data.get(CONF_DEVICE_ID))
            if error is None:
                return self.async_update_reload_and_abort(entry, data={**entry.data, **user_input})
            errors["base"] = error

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=get_reconfigure_schema(entry.data.get(CONF_USERNAME, "")),
            errors=errors,
        )

    async def async_step_reauth(
        self,
        entry_data: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Start reauthentication for an existing entry."""
        entry = self._get_reauth_entry()
        if entry.unique_id is not None:
            await self.async_set_unique_id(entry.unique_id)
            self._abort_if_unique_id_mismatch()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Confirm updated credentials and reload the existing entry."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            error = await self._async_validate_credentials(user_input, entry.data.get(CONF_DEVICE_ID))
            if error is None:
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, **user_input},
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=get_reauth_schema(entry.data.get(CONF_USERNAME, "")),
            errors=errors,
            description_placeholders={"username": entry.data.get(CONF_USERNAME, "")},
        )

    async def _async_validate_credentials(
        self,
        user_input: dict[str, Any],
        device_id: Any = None,
    ) -> str | None:
        """Validate credentials and return the user-facing error key, if any."""
        try:
            devices = await validate_credentials(
                self.hass,
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
            )
            if device_id is not None and not any(device.get("id") == device_id for device in devices):
                return "device_not_found"
        except DaichiCloudClimateApiClientAuthenticationError:
            return "auth"
        except DaichiCloudClimateApiClientCommunicationError:
            return "connection"
        except DaichiCloudClimateApiClientError:
            LOGGER.exception("Unexpected Daichi Cloud API error during config flow")
            return "unknown"
        except Exception:  # noqa: BLE001 - Unexpected config flow errors must be logged and shown as unknown.
            LOGGER.exception("Unexpected error during Daichi Cloud config flow")
            return "unknown"
        return None


__all__ = ["DaichiCloudClimateConfigFlowHandler"]
