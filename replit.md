# TRMNL Sensor Push Integration

## Overview

This is a Home Assistant custom integration that pushes entity data from labeled sensors to TRMNL (Terminal) devices via webhook. The integration allows users to select specific entity groups by labels and automatically sends their state information to a configured TRMNL webhook endpoint at regular intervals.

## System Architecture

### Backend Architecture
- **Framework**: Home Assistant Custom Integration (Python 3.11+)
- **Async HTTP Client**: aiohttp for webhook requests
- **Configuration**: Config flow-based setup with validation
- **Data Processing**: Template-based entity filtering and payload creation
- **Scheduling**: Time-based intervals for data transmission (30 minutes default)

### Integration Pattern
- Cloud push integration (`iot_class: "cloud_push"`)
- Config entry only (no YAML configuration)
- HACS (Home Assistant Community Store) compatible
- No persistent storage requirements

## Key Components

### 1. Main Integration Module (`__init__.py`)
- **Purpose**: Core integration setup and entity data processing
- **Key Functions**:
  - `create_minimal_entity_payload()`: Creates optimized payloads for TRMNL API
  - Config entry management
  - Scheduled data transmission setup
- **Design Decision**: Minimal payload approach to stay within 2KB API limits

### 2. Configuration Flow (`config_flow.py`)
- **Purpose**: User interface for integration setup
- **Features**:
  - URL validation (http/https requirement)
  - Sensor group selection with custom values
  - Multi-select dropdown for label-based filtering
- **Design Decision**: Dynamic sensor group selection to support flexible entity labeling

### 3. Constants (`const.py`)
- **Configuration Keys**: URL and sensor groups
- **Rate Limiting**: 30-minute intervals between updates
- **Payload Limits**: 2KB maximum payload size for TRMNL API
- **Backward Compatibility**: Default "TRMNL" label support

### 4. User Interface Strings (`strings.json`)
- **Localization**: English strings for config flow
- **Error Handling**: Specific error messages for validation failures
- **Options Flow**: Support for reconfiguration after initial setup

## Data Flow

1. **Setup Phase**:
   - User provides TRMNL webhook URL
   - User selects entity groups/labels
   - Integration validates configuration

2. **Runtime Phase**:
   - Timer triggers every 30 minutes
   - Template system filters entities by selected labels
   - Minimal payloads created for each entity
   - Batch HTTP POST to TRMNL webhook
   - Error handling and logging

3. **Data Format**:
   ```json
   {
     "name": "friendly_name_or_entity_id",
     "value": "state_with_unit"
   }
   ```

## External Dependencies

### Core Dependencies
- **Home Assistant Core**: >=2024.3.3
- **aiohttp**: >=3.9.3 (HTTP client)
- **voluptuous**: >=0.13.1 (configuration validation)

### TRMNL API Integration
- **Endpoint**: Custom webhook URL provided by user
- **Method**: HTTP POST
- **Payload Limit**: 2KB maximum
- **Authentication**: URL-based (webhook token embedded)

### Home Assistant Integration Points
- **Labels System**: Uses HA label functionality for entity filtering
- **Template Engine**: Leverages HA template system for entity discovery
- **Config Flow**: Standard HA configuration pattern
- **Event System**: Uses HA's time interval tracking

## Deployment Strategy

### HACS Installation
- **Repository Type**: Custom integration
- **Minimum Versions**: HA 2023.1.0, HACS 1.6.0
- **Installation Path**: `custom_components/trmnl_sensor_push/`

### Configuration Requirements
1. TRMNL webhook URL (format: `https://usetrmnl.com/api/custom_plugins/XXXX-XXXX-XXXX-XXXX`)
2. At least one sensor group/label selection
3. Entities must be properly labeled in Home Assistant

### Runtime Considerations
- **Memory**: Minimal memory footprint (no persistent storage)
- **Network**: Periodic outbound HTTPS requests only
- **Performance**: Optimized payload size and 30-minute intervals to minimize load

## Changelog

- June 24, 2025. Initial setup

## User Preferences

Preferred communication style: Simple, everyday language.