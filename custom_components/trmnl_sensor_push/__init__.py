"""The TRMNL Entity Push integration."""
from __future__ import annotations

import logging
import json
from datetime import datetime, timedelta
import asyncio
import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.template import Template

from .const import DOMAIN, MIN_TIME_BETWEEN_UPDATES, CONF_URL, CONF_SENSOR_GROUPS, MAX_PAYLOAD_SIZE, DEFAULT_SENSOR_GROUPS

_LOGGER = logging.getLogger(__name__)

# Since this integration only supports config entries, use this schema
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

def create_minimal_entity_payload(state) -> dict:
    """Create minimal payload for a single entity with just name and value."""
    # Use friendly name if available, otherwise use entity_id
    name = state.attributes.get('friendly_name', state.entity_id.split('.')[-1])
    
    # Format the value appropriately
    value = state.state
    unit = state.attributes.get('unit_of_measurement')
    if unit and value not in ['unknown', 'unavailable']:
        try:
            # Try to format numeric values nicely
            float_val = float(value)
            if float_val.is_integer():
                value = f"{int(float_val)}{unit}"
            else:
                value = f"{float_val:.1f}{unit}"
        except (ValueError, TypeError):
            # If not numeric, just append unit if it exists
            if unit:
                value = f"{value}{unit}"
    
    payload = {
        "name": name,
        "value": value
    }
    
    _LOGGER.debug("TRMNL: Created minimal payload for %s: %s", state.entity_id, payload)
    return payload

def calculate_payload_size(payload: dict) -> int:
    """Calculate the size of the payload in bytes."""
    return len(json.dumps(payload, separators=(',', ':')).encode('utf-8'))

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the TRMNL Entity Push component."""
    _LOGGER.debug("TRMNL: Setting up TRMNL Entity Push component")
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TRMNL Entity Push from a config entry."""
    _LOGGER.debug("TRMNL: Setting up config entry")
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    # Get configuration values
    url = entry.data.get(CONF_URL)
    sensor_groups = entry.data.get(CONF_SENSOR_GROUPS, DEFAULT_SENSOR_GROUPS)
    
    # Also check options for updates
    if entry.options:
        url = entry.options.get(CONF_URL, url)
        sensor_groups = entry.options.get(CONF_SENSOR_GROUPS, sensor_groups)
    
    _LOGGER.debug("TRMNL: Using webhook URL: %s", url)
    _LOGGER.debug("TRMNL: Using sensor groups: %s", sensor_groups)

    def get_entities_by_groups(groups: list[str]) -> list[str]:
        """Get entities with specified group labels using template."""
        _LOGGER.debug("TRMNL: Fetching entities for groups: %s", groups)
        all_entities = []
        
        for group in groups:
            _LOGGER.debug("TRMNL: Processing group: %s", group)
            template_str = f"{{{{ label_entities('{group}') }}}}"
            template = Template(template_str, hass)
            try:
                group_entities = template.async_render()
                if group_entities:
                    all_entities.extend(group_entities)
                    _LOGGER.debug("TRMNL: Found %d entities in group '%s'", len(group_entities), group)
                else:
                    _LOGGER.debug("TRMNL: No entities found in group '%s'", group)
            except Exception as err:
                _LOGGER.error("TRMNL: Error processing group '%s': %s", group, err)
        
        # Remove duplicates while preserving order
        unique_entities = list(dict.fromkeys(all_entities))
        _LOGGER.debug("TRMNL: Total unique entities found: %d", len(unique_entities))
        return unique_entities

    async def process_sensor_groups(*_):
        """Find and process entities from configured sensor groups."""
        _LOGGER.debug("TRMNL: Starting entity processing for groups: %s", sensor_groups)
        
        # Create grouped payload structure
        grouped_payload = {}
        total_entities = 0
        
        for group in sensor_groups:
            _LOGGER.debug("TRMNL: Processing group: %s", group)
            template_str = f"{{{{ label_entities('{group}') }}}}"
            template = Template(template_str, hass)
            
            try:
                group_entities = template.async_render()
                if not group_entities:
                    _LOGGER.debug("TRMNL: No entities found in group '%s'", group)
                    continue
                
                # Process entities in this group
                group_payload = []
                for entity_id in group_entities:
                    state = hass.states.get(entity_id)
                    if state and state.state not in ['unknown', 'unavailable']:
                        _LOGGER.debug("TRMNL: Processing entity: %s in group %s", entity_id, group)
                        group_payload.append(create_minimal_entity_payload(state))
                    else:
                        _LOGGER.debug("TRMNL: Skipping entity %s (state: %s)", entity_id, state.state if state else "not found")
                
                # Add group to payload if it has entities
                if group_payload:
                    grouped_payload[group] = group_payload
                    total_entities += len(group_payload)
                    _LOGGER.debug("TRMNL: Added %d entities to group '%s'", len(group_payload), group)
                
            except Exception as err:
                _LOGGER.error("TRMNL: Error processing group '%s': %s", group, err)

        # If no entities found, log error and return
        if not grouped_payload:
            _LOGGER.error("TRMNL: No entities found for groups: %s", sensor_groups)
            return

        # Log the number of entities found
        _LOGGER.info("TRMNL: Found %d entities across %d groups", total_entities, len(grouped_payload))

        # Send to TRMNL webhook if we have entities
        if grouped_payload:
            # Create base payload with grouped structure
            payload = {
                "merge_variables": {
                    **grouped_payload,  # Spread the grouped data directly
                    "timestamp": datetime.now().isoformat(),
                    "total_count": total_entities,
                    "groups": list(grouped_payload.keys())
                }
            }
            
            # Check payload size and handle truncation if needed
            payload_size = calculate_payload_size(payload)
            _LOGGER.debug("TRMNL: Payload size: %d bytes", payload_size)
            
            if payload_size > MAX_PAYLOAD_SIZE:
                _LOGGER.warning("TRMNL: Payload size (%d bytes) exceeds 2KB limit, truncating groups", payload_size)
                
                # Remove entities from groups until we're under the limit
                while payload_size > MAX_PAYLOAD_SIZE and any(grouped_payload.values()):
                    # Find the group with the most entities and remove one
                    largest_group = max(grouped_payload.keys(), key=lambda g: len(grouped_payload[g]))
                    if grouped_payload[largest_group]:
                        grouped_payload[largest_group].pop()
                        # Remove empty groups
                        if not grouped_payload[largest_group]:
                            del grouped_payload[largest_group]
                        
                        # Update payload
                        payload["merge_variables"] = {
                            **grouped_payload,
                            "timestamp": datetime.now().isoformat(),
                            "total_count": sum(len(entities) for entities in grouped_payload.values()),
                            "groups": list(grouped_payload.keys())
                        }
                        payload_size = calculate_payload_size(payload)
                    else:
                        break
                
                _LOGGER.info("TRMNL: Reduced payload to %d entities (%d bytes)", 
                           sum(len(entities) for entities in grouped_payload.values()), payload_size)
            
            _LOGGER.debug("TRMNL: Preparing to send grouped payload with %d groups", len(grouped_payload))
            
            try:
                async with aiohttp.ClientSession() as session:
                    _LOGGER.debug("TRMNL: Sending POST request to %s", url)
                    async with session.post(url, json=payload, timeout=30) as response:
                        if response.status == 200:
                            _LOGGER.info("TRMNL: Successfully sent %d entities from %d groups", 
                                       sum(len(entities) for entities in grouped_payload.values()), len(grouped_payload))
                            response_text = await response.text()
                            _LOGGER.debug("TRMNL: Webhook response: %s", response_text)
                        else:
                            _LOGGER.error("TRMNL: Error sending to webhook: HTTP %s", response.status)
                            response_text = await response.text()
                            _LOGGER.error("TRMNL: Response: %s", response_text)
            except asyncio.TimeoutError:
                _LOGGER.error("TRMNL: Timeout sending data to webhook")
            except Exception as err:
                _LOGGER.error("TRMNL: Failed to send data to webhook: %s", err)
        else:
            _LOGGER.debug("TRMNL: No valid entities to send")

    # Set up periodic timer
    _LOGGER.debug("TRMNL: Setting up periodic timer for %d seconds", MIN_TIME_BETWEEN_UPDATES)
    remove_timer = async_track_time_interval(
        hass,
        process_sensor_groups,
        timedelta(seconds=MIN_TIME_BETWEEN_UPDATES)
    )

    # Store the timer removal function
    hass.data[DOMAIN][entry.entry_id]["remove_timer"] = remove_timer

    # Run initial scan
    _LOGGER.debug("TRMNL: Running initial entity scan")
    await process_sensor_groups()

    _LOGGER.info("TRMNL: Integration setup completed for %d groups: %s", len(sensor_groups), sensor_groups)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    try:
        # Remove the timer
        if entry.entry_id in hass.data[DOMAIN]:
            _LOGGER.debug("TRMNL: Removing timer and cleaning up")
            hass.data[DOMAIN][entry.entry_id]["remove_timer"]()
            hass.data[DOMAIN].pop(entry.entry_id)
            _LOGGER.info("TRMNL: Successfully unloaded integration")
    except Exception as err:
        _LOGGER.error("TRMNL: Error unloading integration: %s", err)
        return False
    return True

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
