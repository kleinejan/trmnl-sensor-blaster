"""Config flow for TRMNL Entity Push integration."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .const import DOMAIN, CONF_URL, CONF_SENSOR_GROUPS, DEFAULT_SENSOR_GROUPS

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Optional(CONF_SENSOR_GROUPS, default=DEFAULT_SENSOR_GROUPS): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[],
                mode=selector.SelectSelectorMode.DROPDOWN,
                multiple=True,
                custom_value=True,
            )
        ),
    }
)

async def validate_input(hass: HomeAssistant, data: dict[str, str]) -> dict[str, str]:
    """Validate the user input allows us to connect."""
    # Validate URL format
    url = data.get(CONF_URL, "")
    if not url.startswith(("http://", "https://")):
        raise InvalidURL("URL must start with http:// or https://")
    
    # Validate sensor groups
    sensor_groups = data.get(CONF_SENSOR_GROUPS, [])
    if not sensor_groups:
        raise NoSensorGroups("At least one sensor group must be specified")
    
    return {"title": f"TRMNL Push ({len(sensor_groups)} groups)"}

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TRMNL Entity Push."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._data = {}

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except InvalidURL:
                errors["base"] = "invalid_url"
            except NoSensorGroups:
                errors["base"] = "no_sensor_groups"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        # Get available labels from Home Assistant
        available_labels = await self._get_available_labels()
        
        # Update schema with available labels
        schema = vol.Schema(
            {
                vol.Required(CONF_URL, default=user_input.get(CONF_URL, "") if user_input else ""): str,
                vol.Required(
                    CONF_SENSOR_GROUPS, 
                    default=user_input.get(CONF_SENSOR_GROUPS, DEFAULT_SENSOR_GROUPS) if user_input else DEFAULT_SENSOR_GROUPS
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=available_labels,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        multiple=True,
                        custom_value=True,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def _get_available_labels(self) -> list[str]:
        """Get available labels from Home Assistant."""
        try:
            # Get all labels from the label registry
            label_registry = await self.hass.helpers.label_registry.async_get_registry()
            labels = [label.label_id for label in label_registry.labels.values()]
            return sorted(labels) if labels else DEFAULT_SENSOR_GROUPS
        except Exception:
            return DEFAULT_SENSOR_GROUPS

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for TRMNL Entity Push."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}

        if user_input is not None:
            try:
                await validate_input(self.hass, {**self.config_entry.data, **user_input})
            except InvalidURL:
                errors["base"] = "invalid_url"
            except NoSensorGroups:
                errors["base"] = "no_sensor_groups"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="", data=user_input)

        # Get available labels
        available_labels = await self._get_available_labels()
        
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_URL,
                    default=self.config_entry.options.get(
                        CONF_URL, self.config_entry.data.get(CONF_URL, "")
                    ),
                ): str,
                vol.Required(
                    CONF_SENSOR_GROUPS,
                    default=self.config_entry.options.get(
                        CONF_SENSOR_GROUPS, self.config_entry.data.get(CONF_SENSOR_GROUPS, DEFAULT_SENSOR_GROUPS)
                    ),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=available_labels,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        multiple=True,
                        custom_value=True,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )

    async def _get_available_labels(self) -> list[str]:
        """Get available labels from Home Assistant."""
        try:
            label_registry = await self.hass.helpers.label_registry.async_get_registry()
            labels = [label.label_id for label in label_registry.labels.values()]
            return sorted(labels) if labels else DEFAULT_SENSOR_GROUPS
        except Exception:
            return DEFAULT_SENSOR_GROUPS

class InvalidURL(HomeAssistantError):
    """Error to indicate invalid URL format."""

class NoSensorGroups(HomeAssistantError):
    """Error to indicate no sensor groups specified."""
